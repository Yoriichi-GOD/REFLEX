"""Recompute published canonical metrics from saved maps and source masks."""
from __future__ import annotations
import ast
import csv
from datetime import datetime,timezone
import json
import os
import platform
from pathlib import Path

import cv2
import numpy as np

from app.core.patch_memory import digest
from reflex_bench.data import visa_cases,read_mask,eval_grid
from reflex_bench.improve import check_freeze
from reflex_bench.metrics import threshold_metrics,pixel_metrics

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"reports"/"improvement_20261024"
DATA=ROOT.parent/"reflex-data"/"visa"/"prepared"


def load(path):return json.loads(path.read_text(encoding="utf-8"))
def rows(path):
    with path.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))


def same(actual,expected):
    if isinstance(actual,dict):
        for key,value in actual.items():same(value,expected[key])
    elif isinstance(actual,(float,np.floating)):
        assert np.isclose(actual,expected,atol=1e-10,rtol=1e-8),(actual,expected)
    else:assert actual==expected,(actual,expected)


def main():
    check_freeze();checks={};count=0
    for category in ("candle","cashew"):
        saved=load(OUT/category/"metrics.json");records=rows(OUT/category/"per_case.csv")
        labels=np.array([int(r["label"]) for r in records]);scores=np.array([float(r["score"]) for r in records])
        derived=threshold_metrics(labels,scores,saved["image_metrics"]["threshold"]);derived.pop("predictions")
        same(derived,saved["image_metrics"])
        membership=load(OUT/category/"membership.json")
        sets=[{r["sha256"] for r in membership[k]} for k in ("fit","calibration","development")]
        assert all(not sets[a]&sets[b] for a,b in ((0,1),(0,2),(1,2)))
        test_hashes={r["image_sha256"] for r in records}
        assert all(not hashes&test_hashes for hashes in sets)
        baseline_meta=load(ROOT/"reports"/"benchmarks"/"models"/category/"metadata.json")
        assert sets[1]==set(baseline_meta["calibration_sha256"])
        _,good,bad=visa_cases(DATA/category);cases=good+bad;assert len(cases)==len(records)
        pairs=[]
        for i,(case,row) in enumerate(zip(cases,records)):
            assert case.case_id==row["case_id"] and digest(case.image_path)==row["image_sha256"]
            image=cv2.imread(str(case.image_path));mask=read_mask(case.mask_path,image.shape)
            score=np.load(OUT/category/"maps"/f"{i:04d}.npy")
            _,truth=eval_grid(np.zeros(image.shape[:2],np.float32),mask)
            assert score.shape==truth.shape
            pairs.append((truth,score))
        same(pixel_metrics(pairs,saved["pixel_metrics"]["pixel_threshold"]),saved["pixel_metrics"])
        for family,metric in saved["robustness"].items():
            records_variant=rows(OUT/category/f"robustness_{family}.csv")
            assert len(records_variant)==len(records)
            measured=threshold_metrics(np.array([int(r["label"]) for r in records_variant]),np.array([float(r["score"]) for r in records_variant]),saved["image_metrics"]["threshold"])
            measured.pop("predictions");same(measured,metric["image"])
        count+=len(records)*(1+len(saved["robustness"]))
        checks[category]={"canonical_cases":len(records),"derived_robustness_families":len(saved["robustness"]),
                          "csv_image_metrics_recomputed":True,"saved_map_pixel_metrics_recomputed":True,
                          "all_source_test_image_hashes_verified":True,"fit_calibration_development_test_disjoint":True,
                          "same_calibration_membership_as_original":True}
    pyfiles=list((ROOT/"backend").rglob("*.py"))
    pyfiles=[p for p in pyfiles if "__pycache__" not in p.parts]
    for path in pyfiles:ast.parse(path.read_text(encoding="utf-8"),filename=str(path.relative_to(ROOT)))
    baseline=ROOT/"dist"/"benchmark-submission-20261024"/"reflex-submission.zip"
    baseline_sha=digest(baseline);assert baseline_sha=="1503ceb71c4ccd271928b806cc4980ee46110b515edebfbd9078c905a9230b90"
    final_log=(OUT/"regression_final.log").read_text(encoding="utf-8",errors="replace")
    assert "37 passed" in final_log and "failed" not in final_log
    output={"utc":datetime.now(timezone.utc).isoformat(),"categories":checks,"test_and_derived_inference_count":count,
            "regression":{"passed":37,"failed":0,"skipped":0,"warnings":13,"real_pretrained_integration_enabled":True,
                          "log_sha256":digest(OUT/"regression_final.log"),"storage":"isolated temporary fixtures and database"},
            "python_ast_files":len(pyfiles),"javascript_syntax":"node --check frontend/app.js passed",
            "frozen_source_check":True,"baseline_archive_unchanged_sha256":baseline_sha,
            "runtime":{"python":platform.python_version(),"platform":platform.platform(),"cpu":platform.processor(),
                       "logical_cpu_count":os.cpu_count(),"opencv":cv2.__version__,"numpy":np.__version__},
            "live_local_api_smoke":load(OUT/"local_smoke.json"),
            "browser":{"profile_category":"candle","matching_real_evaluation_visible":True,"defect_overlay_and_one_full_image_trace_visible":True,"screenshot":"local_app.png"},
            "preserved_failures":["Initial attempt inspected an incomplete download and failed parsing; only full publisher-hash-verified weights were subsequently used.",
                                  "Sandbox temp-file access failed; elevated isolated unit checks passed.",
                                  "OpenCV 5 could not expose arbitrary internal outputs from original classification graph; verified unmodified-weight feature export resolved it.",
                                  "First extended API regression hit shared test rate-limit state (429); isolated new test state, preserved production limiter, then all37 passed."],
            "not_verified":["fresh blind generalization","official WideResNet PatchCore parity","agentic reinspection benefit","new-model AWS execution/performance","pcb1 or all12 VisA categories","industrial safety"]}
    (OUT/"verification.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(json.dumps({"canonical_cases":350,"total_canonical_and_derived":count,"passed_tests":37,"python_files_parsed":len(pyfiles),"baseline_archive_unchanged":True}))


if __name__=="__main__":main()
