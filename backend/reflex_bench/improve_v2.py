"""Predeclared normal-only v2 fits and frozen evaluation. No test tuning."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import cv2
import numpy as np
from reflex_bench.runtime_stats_v2 import memory_snapshot

from app.core.patch_memory import PatchMemory,digest
from app.core.patch_memory_v2 import (PatchConfig,PatchMemoryV2,fit_detail,tile_boxes,choose_tile,random_tile,grid_map,restore_map)
from app.agent.patch_policy_v2 import run_v2_policy
from app.core.model import render_evidence,fit_normal_bank,load_bank,analyze as classical_analyze,extract_regions
from app.core.quality import inspect_quality
from reflex_bench.data import Case,visa_cases,read_mask,eval_grid
from reflex_bench.metrics import threshold_metrics,decision_metrics,area_slices
from reflex_bench.metrics_v2 import pixel_metrics
from reflex_bench.evaluate import _latency,_region_metrics
from reflex_bench.robustness import _variants

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"reports/improvement_v2_20261024"
DATA=Path(os.getenv("REFLEX_VISA_PREPARED",str(ROOT.parent/"reflex-data/visa/prepared")))
WEIGHTS=Path(os.getenv("REFLEX_ONNX_WEIGHTS",str(ROOT.parent/"reflex-data/models/resnet50-v1-12.onnx")))
ARMS=["dense128_region","dense128_max","dense128_top4","dense512_max","dense128_pose",
      "dense128_seed20261025","dense128_seed20261026","dense512_seed20261025","dense512_seed20261026"]
FRESH=ROOT.parent/"reflex-data/reference_20261024"
FRESH_CATEGORIES=("capsules","chewinggum","pcb1")
EXPECTED_MASK_SHA={}


def fresh_root(category):
    return ROOT.parent/"reflex-data/reference_pcb1_20261024" if category=="pcb1" else FRESH


def manifest_root(category):
    return fresh_root(category)/("manifests" if category=="pcb1" else "manifests_v2")


def verified_manifest(category,role):
    folder=manifest_root(category)
    frozen=json.loads((folder/"freeze.json").read_text())
    path=folder/f"{role}.json"
    if digest(path)!=frozen["manifest_sha256"][path.name]:
        raise RuntimeError(f"Sealed manifest changed: {path}")
    return json.loads(path.read_text())


def data_root(category):
    return fresh_root(category)/"prepared" if category in FRESH_CATEGORIES else DATA


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2),encoding="utf-8")


def csv_write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def _members(category):
    if category in FRESH_CATEGORIES:
        result={}
        for group,source in (("fit","fit"),("calibration","calibration"),("development","train_development")):
            rows=[r for r in verified_manifest(category,source) if r["category"]==category]
            assert rows and all(r["label"]==0 and r["official_split"]=="train" for r in rows)
            result[group]=[Path(r["image_path"]) for r in rows]
            assert all(digest(p)==r["image_sha256"] for p,r in zip(result[group],rows))
        sets=[{digest(p) for p in v} for v in result.values()]
        assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
        return result
    manifest=json.loads((ROOT/f"reports/improvement_20261024/{category}/membership.json").read_text())
    result={}
    for group in ("fit","calibration","development"):
        result[group]=[DATA/category/"train/good"/r["file"] for r in manifest[group]]
        assert all(digest(path)==r["sha256"] for path,r in zip(result[group],manifest[group]))
    sets=[{digest(p) for p in v} for v in result.values()]
    assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
    return result


def profile(category,arm):
    return OUT/"models"/category/arm


def train(category):
    members=_members(category)
    if category in FRESH_CATEGORIES:
        directory=profile(category,"v1_fresh")
        if not (directory/"metadata.json").exists():
            old=PatchMemory(WEIGHTS)
            old.fit(members["fit"],members["calibration"],directory,category)
    for dim in (128,512):
        for seed in (20261024,20261025,20261026):
            arm=("dense128_region" if dim==128 else "dense512_max") if seed==20261024 else f"dense{dim}_seed{seed}"
            directory=profile(category,arm)
            if (directory/"metadata.json").exists():
                print(json.dumps({"phase":"resume_existing_fit","category":category,"arm":arm}),flush=True)
                model=PatchMemoryV2.load(directory,WEIGHTS)
            else:
                model=PatchMemoryV2(WEIGHTS,PatchConfig(dimensions=dim,seed=seed,scoring="region" if dim==128 else "max"))
                model.fit(members["fit"],members["calibration"],directory,category)
                model.calibrate_review(members["development"])
                model.save(directory)
            print(json.dumps({"phase":"fitted","category":category,"arm":arm,"config":asdict(model.config),
                              "threshold":model.metadata["image_threshold"],"pass_quantile":model.metadata["pass_quantile"],
                              "seconds":model.metadata["fit_and_calibration_seconds"]}),flush=True)
            if dim==128 and seed==20261024:
                primary=model
                for scoring in ("max","top4"):
                    sub=profile(category,f"dense128_{scoring}")
                    if not (sub/"metadata.json").exists():
                        variant=PatchMemoryV2.load(directory,WEIGHTS)
                        variant.set_operation(scoring)
                        variant.calibrate_review(members["development"])
                        variant.save(sub)
    directory=profile(category,"dense128_pose")
    if not (directory/"metadata.json").exists():
        model=PatchMemoryV2(WEIGHTS,PatchConfig(scoring="max",pose_augmentation=True))
        model.fit(members["fit"],members["calibration"],directory,category)
        model.calibrate_review(members["development"])
        model.save(directory)
    primary=PatchMemoryV2.load(profile(category,"dense128_region"),WEIGHTS)
    detail_dir=profile(category,"dense128_region")/"detail"
    if not (detail_dir/"metadata.json").exists():
        fit_detail(members["fit"],members["calibration"],primary,detail_dir)
    primary.metadata["detail_directory"]="detail"
    suitability=ROOT/f"reports/suitability_v2_20261024/run/{category}_metadata.json"
    if suitability.exists():
        primary.metadata["suitability"]=json.loads(suitability.read_text())
    primary.save(profile(category,"dense128_region"))
    print(json.dumps({"phase":"training_complete","category":category}),flush=True)


def train_classical(category):
    members=_members(category)
    directory=profile(category,"classical_cv5")
    if (directory/"metadata.json").exists():
        load_bank(directory)
        print(json.dumps({"phase":"resume_classical","category":category}),flush=True)
        return
    started=time.perf_counter()
    fit_normal_bank(members["fit"],members["calibration"],directory,seed=20261024,source=f"visa:{category}")
    print(json.dumps({"phase":"classical_fit_complete","category":category,"seconds":time.perf_counter()-started}),flush=True)


def freeze(categories):
    legacy=json.loads((ROOT/"reports/improvement_20261024/freeze.json").read_text())
    for path,expected in legacy["files"].items():
        if digest(ROOT/path)!=expected:raise RuntimeError(f"Historical frozen artifact changed: {path}")
    paths=[ROOT/p for p in ("backend/app/core/patch_memory_v2.py","backend/app/agent/patch_policy_v2.py",
                            "backend/reflex_bench/improve_v2.py","backend/reflex_bench/runtime_stats_v2.py",
                            "backend/app/core/engine.py","backend/app/agent/controller.py","backend/app/main.py","frontend/app.js",
                            "backend/reflex_bench/metrics.py","backend/reflex_bench/metrics_v2.py","backend/reflex_bench/data.py","backend/app/core/model.py",
                            "reports/improvement_v2_20261024/PROTOCOL.md",
                            "reports/improvement_v2_20261024/PROTOCOL_EVALUATOR_ADDENDUM.md")]
    suitability=ROOT/"backend/app/core/suitability_v2.py"
    if suitability.exists():paths.append(suitability)
    for c in categories:
        for arm in ARMS:
            for name in ("metadata.json","patch_bank.npz"):
                paths.append(profile(c,arm)/name)
        paths.extend((profile(c,"dense128_region")/"detail"/n) for n in ("metadata.json","patch_bank.npz"))
        paths.extend(profile(c,"classical_cv5")/n for n in ("metadata.json","normal_bank.npz"))
        if c in FRESH_CATEGORIES:
            paths.extend(profile(c,"v1_fresh")/n for n in ("metadata.json","patch_bank.npz"))
            paths.extend(manifest_root(c)/f"{n}.json" for n in ("freeze","fit","calibration","train_development","development","final"))
    value={"utc":datetime.now(timezone.utc).isoformat(),"categories":categories,"primary":"dense128_region",
           "files":{str(p.resolve()):digest(p) for p in paths},"weights_sha256":digest(WEIGHTS),
           "legacy_frozen_artifacts_verified":len(legacy["files"]),
           "threshold_selection":"normalcalibrationonly; review selection normaldevelopmentonly; primary fixed before evaluation"}
    path=OUT/"freeze.json"
    if path.exists():
        old=json.loads(path.read_text());assert old["files"]==value["files"],"Existing evaluation freeze differs"
    else:write(path,value)
    print(json.dumps({"phase":"frozen","files":len(paths)}),flush=True)


def check_freeze():
    frozen=json.loads((OUT/"freeze.json").read_text())
    for rel,expected in frozen["files"].items():
        if digest(Path(rel))!=expected:raise RuntimeError(f"Frozen v2 artifact changed: {rel}")


def eval_cases(category,split):
    if category not in FRESH_CATEGORIES:
        _,good,bad=visa_cases(DATA/category)
        with (ROOT/f"reports/improvement_20261024/{category}/per_case.csv").open(newline="",encoding="utf-8") as handle:
            known={r["case_id"]:r["mask_sha256"] for r in csv.DictReader(handle)}
        for case in bad:EXPECTED_MASK_SHA[str(case.mask_path)]=known[case.case_id]
        return good+bad
    if split not in ("development","final"):raise ValueError("Fresh evaluation needs explicit sealed split")
    rows=[r for r in verified_manifest(category,split) if r["category"]==category]
    cases=[]
    for r in rows:
        image=Path(r["image_path"]);mask=Path(r["mask_path"]) if r["mask_path"] else None
        assert digest(image)==r["image_sha256"]
        if mask is not None:EXPECTED_MASK_SHA[str(mask)]=r["prepared_mask_sha256"]
        cases.append(Case(f"{'bad' if r['label'] else 'good'}/{image.name}",image,mask,r["label"],f"VisA custom{split}sealed"))
    return cases


def checked_mask(case,image):
    """Call only after canonical prediction; metadata binds evaluator mask bytes."""
    if case.mask_path is not None:
        expected=EXPECTED_MASK_SHA[str(case.mask_path)]
        if digest(case.mask_path)!=expected:raise RuntimeError(f"Evaluation mask changed: {case.mask_path}")
    return read_mask(case.mask_path,image.shape)


def _threshold(labels,scores,threshold):
    value=threshold_metrics(np.array(labels),np.array(scores),threshold);value.pop("predictions")
    return value


def evaluate(category,split="replay"):
    check_freeze()
    cases=eval_cases(category,split)
    for arm in ARMS:
        target=OUT/"evaluation"/category/(split if split!="replay" else "")/arm
        if (target/"metrics.json").exists():continue
        target.mkdir(parents=True,exist_ok=True)
        model=PatchMemoryV2.load(profile(category,arm),WEIGHTS)
        rows=[];pairs=[];raw_maps=[];fractions=[];decisions=[];native_counts=np.zeros(4,dtype=np.int64)
        peak=memory_snapshot()["rss_bytes"]
        for index,case in enumerate(cases):
            image=cv2.imread(str(case.image_path))
            start=time.perf_counter();result=model.analyze(image);elapsed=(time.perf_counter()-start)*1000
            # Ground truth is only opened after all model/agent inputs are computed.
            agent=run_v2_policy(image,result)
            truth=checked_mask(case,image)
            if arm=="dense128_region":
                hot=result["score_map"]>result["pixel_threshold"];gt=truth>0
                native_counts+=np.array([np.sum(hot & gt),np.sum(hot & ~gt),np.sum(~hot & gt),np.sum(~hot & ~gt)],dtype=np.int64)
            score,mask=eval_grid(result["score_map"],truth)
            pairs.append((mask,score));fractions.append(float(truth.mean()));decisions.append(agent["decision"])
            raw_maps.append((result["raw_patch_map"],result["letterbox"],image.shape[:2],mask))
            second=result.get("second_look")
            rows.append({"case_id":case.case_id,"label":case.label,"image_sha256":digest(case.image_path),
                         "mask_sha256":digest(case.mask_path) if case.mask_path else "",
                         "score":result["score"],"threshold":result["threshold"],"pass_threshold":result["pass_threshold"],
                         "max_patch_score":result["all_scores"]["max"],"top4_patch_score":result["all_scores"]["top4"],
                         "region_patch_score":result["all_scores"]["region"],
                         "pixel_threshold":result["pixel_threshold"],"prediction":int(result["score"]>result["threshold"]),
                         "decision":agent["decision"],"quality_flags":"|".join(result["quality"]["flags"]),
                         "suitability_warnings":"|".join(result["quality"].get("suitability",{}).get("flags",[])),
                         "second_look":bool(second),"detail_score":second["crop_anomaly_score"] if second else None,
                         "detail_threshold":second["calibrated_image_threshold"] if second else None,
                         "detail_bbox_json":json.dumps(second["source_bbox_xyxy"]) if second else None,
                         "detail_error":second.get("tool_error") if second else None,
                         "agent_trace_json":json.dumps(agent["agent_trace"],separators=(",",":")),
                         "elapsed_ms_with_feature_cache":elapsed,"process_rss_bytes":memory_snapshot()["rss_bytes"]})
            peak=max(peak,memory_snapshot()["rss_bytes"])
            if arm=="dense128_region":
                (target/"maps").mkdir(exist_ok=True)
                np.save(target/"maps"/f"{index:04d}.npy",score)
                (target/"raw_maps").mkdir(exist_ok=True)
                np.savez(target/"raw_maps"/f"{index:04d}.npz",raw=result["raw_patch_map"],box=result["letterbox"],shape=image.shape[:2])
            if (index+1)%50==0:print(json.dumps({"phase":"evaluate","category":category,"arm":arm,"done":index+1}),flush=True)
        csv_write(target/"per_case.csv",rows)
        y=[r["label"] for r in rows];s=[r["score"] for r in rows]
        pixel=pixel_metrics(pairs,model.metadata["pixel_threshold"])
        values={"category":category,"arm":arm,"primary":arm=="dense128_region","source":"VisA reused official test development replay" if split=="replay" else f"VisA new-categorycustom{split};notfreshfactorycaptures",
                "image_metrics":_threshold(y,s,model.metadata["image_threshold"]),"pixel_metrics":pixel,
                "region_metrics":_region_metrics([(m,s>model.metadata["pixel_threshold"]) for m,s in pairs]),
                "area_slices":area_slices(np.array(y),np.array(s),model.metadata["image_threshold"],np.array(fractions)),
                "decisions":decision_metrics(np.array(y),decisions),"second_look_count":sum(r["second_look"] for r in rows),
                "model_sha256":model.metadata["normal_bank_sha256"],"config":asdict(model.config),
                "process_peak_observed_rss_bytes":peak,"timing_scope":"feature-cache-enabled experiment; not production latency"}
        if arm=="dense128_region":
            tp,fp,fn,tn=map(int,native_counts)
            values["native_pixel_metrics"]={"scope":"original-coordinate pixel threshold counts; no native AUROC/AP computed",
                "TP":tp,"FP":fp,"FN":fn,"TN":tn,"precision":tp/max(tp+fp,1),"recall":tp/max(tp+fn,1),
                "iou":tp/max(tp+fp+fn,1),"dice":2*tp/max(2*tp+fp+fn,1)}
            alternatives={}
            for sigma in (1.,4.):
                alt_pairs=[(mask,grid_map(restore_map(raw,box,shape,sigma))) for raw,box,shape,mask in raw_maps]
                # Score ranking statistics need only be sorted once per sigma.
                for q in (.995,.9975,.999):
                    threshold=model.metadata["pixel_thresholds"][str(sigma)][str(q)]
                    if sigma==1. and q==.9975: alternatives[f"sigma{sigma}_q{q}"]=pixel
                    else: alternatives[f"sigma{sigma}_q{q}"]=pixel_metrics(alt_pairs,threshold)
            values["localization_ablation"]=alternatives
        write(target/"metrics.json",values)
        print(json.dumps({"phase":"evaluated","category":category,"arm":arm,"image":values["image_metrics"],"decisions":values["decisions"]}),flush=True)
    if category in FRESH_CATEGORIES:
        evaluate_fresh_v1(category,split,cases)
    else:
        evaluate_legacy_metrics(category,cases)
    evaluate_classical(category,split,cases)


def evaluate_legacy_metrics(category,cases):
    """New metric revision on preserved predictions; no detector refit or rerun."""
    target=OUT/"evaluation"/category/"v1_recomputed_metrics"
    if (target/"metrics.json").exists():return
    original=ROOT/f"reports/improvement_20261024/{category}"
    saved=json.loads((original/"metrics.json").read_text())
    with (original/"per_case.csv").open(newline='',encoding='utf-8') as handle:records=list(csv.DictReader(handle))
    assert len(cases)==len(records)
    pairs=[]
    for index,(case,row) in enumerate(zip(cases,records)):
        assert case.case_id==row['case_id'] and digest(case.image_path)==row['image_sha256']
        image=cv2.imread(str(case.image_path));truth=checked_mask(case,image)
        score=np.load(original/'maps'/f'{index:04d}.npy',allow_pickle=False)
        _,gt=eval_grid(np.zeros(image.shape[:2],np.float32),truth)
        pairs.append((gt,score))
    revised={"category":category,"arm":"v1","source":"Preservedv1predictions;noscoreorcounterfactualchanges",
             "image_metrics":saved['image_metrics'],"decisions":saved['decisions'],
             "pixel_metrics":pixel_metrics(pairs,saved['pixel_metrics']['pixel_threshold']),
             "metric_revision_scope":"Originalpredictionsunchanged;correctedAU-PRO;olderAU-PROinvalidandsuperseded;originalfilesretained"}
    write(target/'metrics.json',revised)
    csv_write(target/'per_case.csv',records)


def evaluate_classical(category,split,cases):
    target=OUT/"evaluation"/category/(split if split!="replay" else "")/"classical_cv5"
    if (target/"metrics.json").exists():return
    mean,scale,meta=load_bank(profile(category,"classical_cv5"))
    records=[];pairs=[];decisions=[]
    for case in cases:
        image=cv2.imread(str(case.image_path));result=classical_analyze(image,mean,scale,meta)
        decision="NEEDS_REVIEW" if result["quality"]["flags"] else "DEFECT_FOUND" if result["score"]>result["threshold"] else "PASS"
        truth=checked_mask(case,image);score,gt=eval_grid(result["score_map"],truth)
        pairs.append((gt,score));decisions.append(decision)
        records.append({"case_id":case.case_id,"label":case.label,"image_sha256":digest(case.image_path),
                        "score":result["score"],"threshold":result["threshold"],"decision":decision})
    csv_write(target/"per_case.csv",records)
    write(target/"metrics.json",{"category":category,"arm":"classical_cv5","source":f"VisA {split};identicalnormalmemberships;frozenlegacyCV5method",
          "image_metrics":_threshold([r["label"] for r in records],[r["score"] for r in records],meta["image_threshold"]),
          "pixel_metrics":pixel_metrics(pairs,meta["pixel_threshold"]),"decisions":decision_metrics(np.array([r["label"] for r in records]),decisions),
          "model_sha256":meta["normal_bank_sha256"],"preprocessing":"legacy120x90spatialfeatures;notbackbone-matched;maxside256evaluationgrid"})


def evaluate_fresh_v1(category,split,cases):
    target=OUT/"evaluation"/category/split/"v1_fresh"
    if (target/"metrics.json").exists():return
    model=PatchMemory.load(profile(category,"v1_fresh"),WEIGHTS)
    rows=[];pairs=[];decisions=[]
    from app.agent.controller import run_policy
    for case in cases:
        image=cv2.imread(str(case.image_path))
        result=model.analyze(image)
        agent=run_policy(image,result,None,None)
        mask=checked_mask(case,image)
        score,gt=eval_grid(result["score_map"],mask)
        pairs.append((gt,score));decisions.append(agent["decision"])
        rows.append({"case_id":case.case_id,"label":case.label,"score":result["score"],
                     "threshold":result["threshold"],"image_sha256":digest(case.image_path),
                     "mask_sha256":digest(case.mask_path) if case.mask_path else "", "decision":agent["decision"]})
    csv_write(target/"per_case.csv",rows)
    write(target/"metrics.json",{"category":category,"arm":"v1_fresh","source":f"VisAcustom{split};unchangedv1methodfreshfitnormalmembership",
          "image_metrics":_threshold([r["label"] for r in rows],[r["score"] for r in rows],model.metadata["image_threshold"]),
          "pixel_metrics":pixel_metrics(pairs,model.metadata["pixel_threshold"]),
          "decisions":decision_metrics(np.array([r["label"] for r in rows]),decisions),"model_sha256":model.metadata["normal_bank_sha256"]})


def detail_controls(category,split="replay"):
    check_freeze()
    full=PatchMemoryV2.load(profile(category,"dense128_region"),WEIGHTS)
    detail=full.detail_model
    cases=eval_cases(category,split)
    rows=[];policy_results={};fusion_pairs={name:[] for name in ("full_chosen","full_random","full_all4")}
    target=OUT/"detail_controls"/category/(split if split!="replay" else "")
    if (target/"metrics.json").exists():return
    for index,case in enumerate(cases):
        image=cv2.imread(str(case.image_path))
        first=full.predict(image)
        boxes=tile_boxes(image.shape)
        selected=choose_tile(first["score_map"],boxes);random=random_tile(image,detail.config.seed)
        quality=inspect_quality(image)
        analysis={**first,"category":category,"threshold":full.metadata["image_threshold"],"pass_threshold":full.metadata["pass_threshold"],
                  "quality":quality,"regions":extract_regions(grid_map(first["score_map"]),full.metadata["pixel_threshold"],(image.shape[1],image.shape[0])),"second_look":None}
        values=[];milliseconds=[];tile_maps=[]
        for box in boxes:
            x1,y1,x2,y2=box
            start=time.perf_counter();r=detail.predict(image[y1:y2,x1:x2]);milliseconds.append((time.perf_counter()-start)*1000)
            values.append(r["score"])
            tile_maps.append(r["score_map"])
        band=analysis["pass_threshold"]<first["score"]<=analysis["threshold"]
        def policy(which,quality_enabled=True,roi=True):
            current={**analysis,"quality":quality if quality_enabled else {**quality,"flags":[]}}
            if band and roi and not current["quality"]["flags"]:
                chosen=selected if which=="chosen" else random
                current["second_look"]={"source_bbox_xyxy":boxes[chosen],"crop_anomaly_score":values[chosen],
                    "calibrated_image_threshold":detail.metadata["detail_thresholds"][which],
                    "crop_score_exceeds_threshold":values[chosen]>detail.metadata["detail_thresholds"][which],
                    "evidence_id":f"control-{index}-{chosen}","elapsed_ms":milliseconds[chosen]}
            return run_v2_policy(image,current)
        selected_result=policy("chosen");random_result=policy("random")
        static="NEEDS_REVIEW" if quality["flags"] else "DEFECT_FOUND" if first["score"]>analysis["threshold"] and analysis["regions"] else "NEEDS_REVIEW" if first["score"]>analysis["threshold"] else "PASS"
        outcomes={"static_quality_gate":static,"chosen_selective":selected_result["decision"],"random_selective":random_result["decision"],
                  "chosen_quality_gate_off":policy("chosen",False)["decision"],"chosen_roi_off":policy("chosen",roi=False)["decision"]}
        for name,decision in outcomes.items():policy_results.setdefault(name,[]).append(decision)
        truth=checked_mask(case,image)
        for name,indices in (("full_chosen",[selected]),("full_random",[random]),("full_all4",range(4))):
            fused=first["score_map"]/full.metadata["pixel_threshold"]
            for i in indices:
                x1,y1,x2,y2=boxes[i]
                fused[y1:y2,x1:x2]=np.maximum(fused[y1:y2,x1:x2],tile_maps[i]/detail.metadata["pixel_threshold"])
            grid,gt=eval_grid(fused,truth);fusion_pairs[name].append((gt,grid))
        record={"case_id":case.case_id,"label":case.label,"image_sha256":digest(case.image_path),
                     "full_score":first["score"],"full_prediction":int(first["score"]>full.metadata["image_threshold"]),
                     "chosen_tile":selected,"random_tile":random,"chosen_score":values[selected],
                     "random_score":values[random],"all4_score":max(values),
                     "chosen_prediction":int(values[selected]>detail.metadata["detail_thresholds"]["chosen"]),
                     "random_prediction":int(values[random]>detail.metadata["detail_thresholds"]["random"]),
                     "all4_prediction":int(max(values)>detail.metadata["detail_thresholds"]["all4"]),
                     "chosen_elapsed_ms_with_feature_cache":milliseconds[selected],
                     "random_elapsed_ms_with_feature_cache":milliseconds[random],
                     "source_pixels_per_tile":(boxes[0][2]-boxes[0][0])*(boxes[0][3]-boxes[0][1]),
                     "active_trigger":bool(band and not quality["flags"]),"selected_trace_json":json.dumps(selected_result["agent_trace"]),
                     "batch_executor_full_calls":1,"batch_executor_extra_calls":4,
                     **{f"decision_{k}":v for k,v in outcomes.items()}}
        for name,value in (("full_chosen",values[selected]/detail.metadata["detail_thresholds"]["chosen"]),
                           ("full_random",values[random]/detail.metadata["detail_thresholds"]["random"]),
                           ("full_all4",max(values)/detail.metadata["detail_thresholds"]["all4"])):
            record[f"{name}_score"]=max(first["score"]/full.metadata["image_threshold"],value)
        rows.append(record)
        if (index+1)%50==0:print(json.dumps({"phase":"detail_controls","category":category,"done":index+1}),flush=True)
    values={"category":category,"source":"reused VisA development replay; paired derived views, not independent captures",
            "operations_per_image":{"chosen":1,"random":1,"all4":4},"controls":{},"normal_thresholds":detail.metadata["detail_thresholds"]}
    for variant in ("chosen","random","all4"):
        values["controls"][variant]=_threshold([r["label"] for r in rows],[r[f"{variant}_score"] for r in rows],detail.metadata["detail_thresholds"][variant])
        values["controls"][variant]["recovered_full_false_clears"]=sum(r["label"] and not r["full_prediction"] and r[f"{variant}_prediction"] for r in rows)
        values["controls"][variant]["new_alerts_on_full_clear_normals"]=sum(not r["label"] and not r["full_prediction"] and r[f"{variant}_prediction"] for r in rows)
    labels=np.array([r["label"] for r in rows]);baseline=policy_results["static_quality_gate"]
    values["selective_policies"]={name:{"decisions":decision_metrics(labels,decisions),
        "flips":dict(__import__('collections').Counter(f"{a}->{b}" for a,b in zip(baseline,decisions))),
        "logical_extra_model_calls":sum(r["active_trigger"] for r in rows) if name in ("chosen_selective","random_selective") else sum(full.metadata["pass_threshold"]<r["full_score"]<=full.metadata["image_threshold"] for r in rows) if name=="chosen_quality_gate_off" else 0,
        "execution_scope":"counterfactualpolicyreusesfourtilebatchoutputs;notindependentlytimedruntime"}
        for name,decisions in policy_results.items()}
    values["active_trigger_count"]=sum(r["active_trigger"] for r in rows)
    values["active_trace_complete_count"]=sum(r["active_trigger"] and len(json.loads(r["selected_trace_json"]))==2 and json.loads(r["selected_trace_json"])[1]["selected_tool"]=="inspect_calibrated_detail" for r in rows)
    values["fixed_budget_fusion"]={name:{"image":_threshold(labels,[r[f"{name}_score"] for r in rows],1.),
        "pixel":pixel_metrics(pairs,1.),"score_rule":"maxofcomponentnormalizedscores;eachcomponentnormalcalibrated;combinedFPRnotrecalibrated", 
        "extra_calls_per_case":4 if name=="full_all4" else 1} for name,pairs in fusion_pairs.items()}
    values["unsupported_component_ablations"]={"registration":"notpartofv2path;OFFequalsON(noinvocation)","second_physical_view":"notprovided;notinvoked;cropisnotnewview"}
    csv_write(target/"per_case.csv",rows);write(target/"metrics.json",values)
    print(json.dumps(values),flush=True)


def robustness(category,split="replay"):
    check_freeze()
    os.environ.pop("REFLEX_V2_FEATURE_CACHE",None)
    target=OUT/"robustness"/category/(split if split!="replay" else "")
    if (target/"metrics.json").exists():return
    model=PatchMemoryV2.load(profile(category,"dense128_region"),WEIGHTS)
    cases=eval_cases(category,split)
    groups={}
    for index,case in enumerate(cases):
        image=cv2.imread(str(case.image_path))
        mask=checked_mask(case,image) # Evaluator creates labeled derived stress only; canonical prediction already frozen separately.
        for name,(variant,truth) in _variants(image,mask,20261023+index).items():
            start=time.perf_counter();r=model.analyze(variant);ms=(time.perf_counter()-start)*1000
            agent=run_v2_policy(variant,r)
            score,gt=eval_grid(r["score_map"],truth)
            group=groups.setdefault(name,{"rows":[],"pairs":[]})
            group["pairs"].append((gt,score))
            group["rows"].append({"case_id":case.case_id,"label":case.label,"score":r["score"],
                                  "prediction":int(r["score"]>r["threshold"]),"decision":agent["decision"],
                                  "quality_flags":"|".join(r["quality"]["flags"]),
                                  "suitability_warnings":"|".join(r["quality"].get("suitability",{}).get("flags",[])),
                                  "second_look":bool(r["second_look"]),"elapsed_ms_with_feature_cache":ms})
        if (index+1)%25==0:print(json.dumps({"phase":"robustness","category":category,"done":index+1}),flush=True)
    output={"category":category,"scope":"nine deterministic dependent image transforms, no independent capture or camera view","variants":{}}
    for name,g in groups.items():
        rows=g["rows"]
        output["variants"][name]={"image":_threshold([r["label"] for r in rows],[r["score"] for r in rows],model.metadata["image_threshold"]),
                                   "decisions":decision_metrics(np.array([r["label"] for r in rows]),[r["decision"] for r in rows]),
                                   "pixel":pixel_metrics(g["pairs"],model.metadata["pixel_threshold"]),
                                   "second_look_count":sum(r["second_look"] for r in rows)}
        csv_write(target/f"{name}.csv",rows)
    write(target/"metrics.json",output)


def latency(category):
    check_freeze()
    os.environ.pop("REFLEX_V2_FEATURE_CACHE",None)
    _,good,bad=visa_cases(DATA/category)
    cases=good[:10]+bad[:10]
    rows=[]
    for arm in ("v1","dense128_region","dense512_max"):
        start=time.perf_counter()
        model=PatchMemory.load(ROOT/f"reports/improvement_20261024/models/{category}",WEIGHTS) if arm=="v1" else PatchMemoryV2.load(profile(category,arm),WEIGHTS)
        load_ms=(time.perf_counter()-start)*1000
        for _ in range(3):model.analyze(cv2.imread(str(cases[0].image_path)))
        for repeat in range(5):
            for case in cases:
                image=cv2.imread(str(case.image_path))
                start=time.perf_counter();r=model.analyze(image);ms=(time.perf_counter()-start)*1000
                rows.append({"category":category,"arm":arm,"repeat":repeat,"case_id":case.case_id,
                             "latency_ms":ms,"second_look":bool(r.get("second_look")),
                             "rss_bytes":memory_snapshot()["rss_bytes"],"model_load_ms":load_ms})
        del model
    target=OUT/"latency"/category
    csv_write(target/"samples.csv",rows)
    write(target/"summary.json",{"scope":"uncached actual CPU analyze;3warmups/100measuredperarm;20casesrepeated5times;notindependentaccuracy",
          "environment":{"python":platform.python_version(),"platform":platform.platform(),"opencv":cv2.__version__,
                         "opencv_threads":cv2.getNumThreads(),"logical_cpus":os.cpu_count(),"ram_bytes":memory_snapshot()["ram_bytes"]},
          "arms":{a:{**_latency([r["latency_ms"] for r in rows if r["arm"]==a]),
                      "max_observed_rss_bytes":max(r["rss_bytes"] for r in rows if r["arm"]==a),
                      "model_load_ms":next(r["model_load_ms"] for r in rows if r["arm"]==a)}
                  for a in ("v1","dense128_region","dense512_max")}})


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["train","train_classical","freeze","evaluate","detail","robustness","latency"])
    p.add_argument("--category",choices=["candle","cashew","capsules","chewinggum","pcb1"])
    p.add_argument("--split",choices=["replay","development","final"],default="replay");a=p.parse_args()
    cv2.setNumThreads(4)
    if a.command=="freeze":freeze(["candle","cashew","capsules","chewinggum","pcb1"])
    else:
        assert a.category
        if a.command=="evaluate":evaluate(a.category,a.split)
        elif a.command=="detail":detail_controls(a.category,a.split)
        elif a.command=="robustness":robustness(a.category,a.split)
        else:{"train":train,"train_classical":train_classical,"latency":latency}[a.command](a.category)


if __name__=="__main__":main()
