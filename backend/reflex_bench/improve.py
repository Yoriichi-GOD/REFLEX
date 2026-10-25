"""Train-only development and frozen test replay for the patch-memory candidate."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time

import cv2
import numpy as np

from app.core.model import read_bgr, render_evidence
from app.core.patch_memory import PatchMemory, SEED, digest, FEATURE_LAYERS
from reflex_bench.data import visa_cases, split_normal, read_mask, eval_grid, list_images
from reflex_bench.metrics import threshold_metrics, pixel_metrics, area_slices, decision_metrics
from reflex_bench.evaluate import _latency, _region_metrics
from reflex_bench.robustness import _variants

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/"reports"/"improvement_20261024"
DATA = Path(os.getenv("REFLEX_VISA_PREPARED", str(ROOT.parent/"reflex-data"/"visa"/"prepared")))
WEIGHTS = Path(os.getenv("REFLEX_ONNX_WEIGHTS", str(ROOT.parent/"reflex-data"/"models"/"resnet50-v1-12.onnx")))


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2),encoding="utf-8")


def save_rows(path: Path, rows: list[dict]):
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def train(category: str):
    paths = list_images(DATA/category/"train"/"good")
    fitting,calibration=split_normal(paths,SEED)
    shuffled=fitting.copy(); random.Random(SEED).shuffle(shuffled)
    n=max(4,round(len(shuffled)*.1))
    validation,fit=sorted(shuffled[-n:]),sorted(shuffled[:-n])
    model=PatchMemory(WEIGHTS)
    model.layers = FEATURE_LAYERS
    started=time.perf_counter()
    model.fit(fit,calibration,OUT/"models"/category,category)
    rows=[]
    for path in validation:
        image=read_bgr(path)
        h,w=image.shape[:2]
        rotated=cv2.warpAffine(image,cv2.getRotationMatrix2D((w/2,h/2),7,1),(w,h),borderMode=cv2.BORDER_REFLECT_101)
        painted=image.copy(); x,y=w//2,h//2
        cv2.rectangle(painted,(x,y),(x+max(8,w//40),y+max(8,h//40)),(0,0,255),-1)
        for variant,sample in (("normal",image),("normal_rotation_7deg",rotated),("painted_development_probe",painted)):
            result=model.predict(sample)
            rows.append({"file":path.name,"sha256":digest(path),"variant":variant,"score":result["score"],
                         "threshold":model.metadata["image_threshold"],"prediction":int(result["score"]>model.metadata["image_threshold"])})
    manifest={"category":category,"fit":[{"file":p.name,"sha256":digest(p)} for p in fit],
              "calibration":[{"file":p.name,"sha256":digest(p)} for p in calibration],
              "development":[{"file":p.name,"sha256":digest(p)} for p in validation]}
    sets=[{r["sha256"] for r in manifest[k]} for k in ("fit","calibration","development")]
    assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
    write_json(OUT/category/"membership.json",manifest)
    save_rows(OUT/category/"development.csv",rows)
    summary={"category":category,"elapsed_seconds":time.perf_counter()-started,"test_data_accessed":False,
             "variants":{k:{"n":sum(r["variant"]==k for r in rows),"flagged":sum(r["prediction"] for r in rows if r["variant"]==k)} for k in sorted({r["variant"] for r in rows})},
             "note":"Painted probes are synthetic development diagnostics; no claim of real defect accuracy."}
    write_json(OUT/category/"development.json",summary)
    print(json.dumps(summary),flush=True)


def freeze():
    files=[ROOT/p for p in ("backend/app/core/patch_memory.py", "backend/app/core/model.py", "backend/app/core/quality.py",
                           "backend/reflex_bench/data.py", "backend/reflex_bench/metrics.py", "backend/reflex_bench/robustness.py",
                           "backend/scripts/export_feature_graph.py", "backend/requirements.txt", "backend/requirements-benchmark.txt",
                           "docs/IMPROVEMENT_PROTOCOL_20261024.md")]+[Path(__file__)]
    files += [OUT/"models"/c/"metadata.json" for c in ("candle","cashew")]
    write_json(OUT/"freeze.json",{"utc":datetime.now(timezone.utc).isoformat(),"weights_sha256":digest(WEIGHTS),
               "files":{p.relative_to(ROOT).as_posix():digest(p) for p in files},
               "threshold_selection":"normal calibration only; frozen before reused official test replay",
               "opencv":cv2.__version__,"numpy":np.__version__,"opencv_threads":cv2.getNumThreads()})


def check_freeze():
    frozen=json.loads((OUT/"freeze.json").read_text())
    for relative,expected in frozen["files"].items():
        if digest(ROOT/relative)!=expected:
            raise RuntimeError(f"Frozen file changed: {relative}")


def evaluate(category: str, robust: bool = False):
    check_freeze()
    model=PatchMemory.load(OUT/"models"/category,WEIGHTS)
    _,good,bad=visa_cases(DATA/category)
    rows=[]; pairs=[]; fractions=[]; decisions=[]
    families={}
    target=OUT/category
    (target/"maps").mkdir(parents=True,exist_ok=True)
    for index,case in enumerate(good+bad):
        image=read_bgr(case.image_path)
        started=time.perf_counter(); result=model.analyze(image); elapsed=(time.perf_counter()-started)*1000
        # Detector has already returned. Only now load evaluator-only masks/labels.
        truth=read_mask(case.mask_path,image.shape)
        score,mask=eval_grid(result["score_map"],truth)
        pairs.append((mask,score)); fractions.append(float(np.mean(truth)))
        prediction=int(result["score"]>result["threshold"])
        decision="NEEDS_REVIEW" if result["quality"]["flags"] or (prediction and not result["regions"]) else ("DEFECT_FOUND" if prediction else "PASS")
        decisions.append(decision)
        np.save(target/"maps"/f"{index:04d}.npy",score)
        rows.append({"case_id":case.case_id,"label":case.label,"image_sha256":digest(case.image_path),
                     "mask_sha256":digest(case.mask_path) if case.mask_path else "", "score":result["score"],
                     "threshold":result["threshold"],"pixel_threshold":result["pixel_threshold"],"prediction":prediction,
                     "decision":decision,"quality_flags":"|".join(result["quality"]["flags"]),"latency_ms":elapsed})
        if robust:
            for name,(variant,mask_variant) in _variants(image,truth,SEED+index).items():
                t=time.perf_counter(); changed=model.predict(variant); ms=(time.perf_counter()-t)*1000
                entry=families.setdefault(name,{"rows":[],"pairs":[]})
                s,m=eval_grid(changed["score_map"],mask_variant)
                entry["pairs"].append((m,s))
                entry["rows"].append({"case_id":case.case_id,"label":case.label,"score":changed["score"],"latency_ms":ms})
        with (target/"progress.jsonl").open("a",encoding="utf-8") as log:
            log.write(json.dumps(rows[-1])+"\n")
        if (index+1)%25==0:
            print(json.dumps({"phase":"test_replay", "category":category,"done":index+1,"total":len(good+bad),"robustness":robust}),flush=True)
    labels=np.array([r["label"] for r in rows]); scores=np.array([r["score"] for r in rows])
    fixed=threshold_metrics(labels,scores,model.metadata["image_threshold"]);fixed.pop("predictions")
    baseline=json.loads((ROOT/"reports"/"benchmarks"/category/"metrics.json").read_text())
    metrics={"category":category,"source":"VisA official one-class test split, reused after baseline diagnosis", "image_metrics":fixed,
             "pixel_metrics":pixel_metrics(pairs,model.metadata["pixel_threshold"]),
             "region_metrics":_region_metrics([(m,s>model.metadata["pixel_threshold"]) for m,s in pairs]),
             "area_slices":area_slices(labels,scores,model.metadata["image_threshold"],np.array(fractions)),
             "decisions":decision_metrics(labels,decisions),"latency":_latency([r["latency_ms"] for r in rows]),
             "agent_note":"Crop-to-spatial-bank comparison disabled for patch model; no claimed reinspection benefit",
             "model_sha256":model.metadata["normal_bank_sha256"],"baseline_image":baseline["image_metrics"],
             "robustness":{}}
    for name,data in families.items():
        fr=data["rows"]
        metric=threshold_metrics(np.array([r["label"] for r in fr]),np.array([r["score"] for r in fr]),model.metadata["image_threshold"])
        metric.pop("predictions")
        metrics["robustness"][name]={"image":metric,"pixel":pixel_metrics(data["pairs"],model.metadata["pixel_threshold"]),"latency":_latency([r["latency_ms"] for r in fr])}
        save_rows(target/f"robustness_{name}.csv",fr)
    save_rows(target/"per_case.csv",rows)
    write_json(target/"metrics.json",metrics)
    # Deterministic high/low score examples, including missed defects.
    selected=[]
    for label in (0,1):
        ranked=sorted((i for i,r in enumerate(rows) if r["label"]==label),key=lambda i:rows[i]["score"])
        selected+=ranked[:3]+ranked[-3:]
    gallery=target/"gallery";gallery.mkdir(exist_ok=True)
    for i in selected:
        case=(good+bad)[i]; image=read_bgr(case.image_path); mask=read_mask(case.mask_path,image.shape)
        smap=np.load(target/"maps"/f"{i:04d}.npy")
        _,overlay,_=render_evidence(image,smap,model.metadata["pixel_threshold"])
        gt=image.copy();gt[mask>0]=(0,0,255)
        h,w=image.shape[:2];ratio=384/max(h,w);size=(round(w*ratio),round(h*ratio))
        panel=np.hstack([cv2.resize(p,size) for p in (image,overlay,gt)])
        header=np.full((42,panel.shape[1],3),250,np.uint8)
        cv2.putText(header,f"{category} {case.case_id} | truth={case.label} | pred={rows[i]['prediction']} | input / score / GT",(8,25),cv2.FONT_HERSHEY_SIMPLEX,.45,(20,20,20),1)
        cv2.imwrite(str(gallery/f"{i:04d}.jpg"),np.vstack([header,panel]))
    print(json.dumps({"category":category,"image":fixed,"pixel":metrics["pixel_metrics"],"latency":metrics["latency"]}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("stage",choices=["train","freeze","evaluate"])
    parser.add_argument("--category",choices=["candle","cashew"]);parser.add_argument("--robust",action="store_true")
    args=parser.parse_args();cv2.setNumThreads(4)
    if args.stage=="freeze":freeze()
    elif args.stage=="train":train(args.category)
    else:evaluate(args.category,args.robust)


if __name__=="__main__":main()
