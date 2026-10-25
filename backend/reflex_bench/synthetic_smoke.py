"""Deterministic QA on the supplied synthetic kit; never a real-world benchmark."""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import cv2
import numpy as np

from app.agent.controller import run_policy
from app.core.model import analyze, fit_normal_bank, load_bank
from reflex_bench.data import eval_grid, sha256_file, split_normal
from reflex_bench.metrics import decision_metrics, pixel_metrics, threshold_metrics

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "data" / "REFLEX_SAMPLE_KIT"
OUT = ROOT / "reports" / "synthetic_qa"
SEED = 20261023


def main() -> None:
    rows = list(csv.DictReader((KIT / "manifest.csv").open(encoding="utf-8-sig", newline="")))
    if any(r.get("is_synthetic", "").lower() != "true" for r in rows):
        raise ValueError("Synthetic QA accepts only rows explicitly marked synthetic")
    results, per_case = [], []
    for category in sorted({r["category"] for r in rows}):
        cat = [r for r in rows if r["category"] == category]
        good = sorted([r for r in cat if r["label"] == "0"], key=lambda r: r["case_id"])
        defect = sorted([r for r in cat if r["label"] == "1"], key=lambda r: r["case_id"])
        shuffled_good = list(good)
        random.Random(SEED + sum(map(ord, category))).shuffle(shuffled_good)
        fit_rows, calibration_rows, eval_normals = shuffled_good[:8], shuffled_good[8:12], shuffled_good[12:]
        if len(fit_rows) != 8 or len(calibration_rows) != 4 or len(eval_normals) != 4:
            raise AssertionError(f"Unexpected normal partition for {category}: {len(fit_rows)}/{len(calibration_rows)}/{len(eval_normals)}")
        train = [KIT / r["path"] for r in fit_rows]
        calibration = [KIT / r["path"] for r in calibration_rows]
        model_dir = OUT / "models" / category
        meta = fit_normal_bank(train, calibration, model_dir, seed=SEED, source="synthetic")
        mean, scale, meta = load_bank(model_dir)
        ys, scores, decisions, pixel_pairs = [], [], [], []
        for row in eval_normals + defect:
            ip = KIT / row["path"]
            mp = KIT / row["mask_path"]
            image = cv2.imread(str(ip), cv2.IMREAD_COLOR)
            mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            if image is None or mask is None:
                raise ValueError(f"Decode failed: {row['case_id']}")
            result = analyze(image, mean, scale, meta)
            policy = run_policy(image, result, mean, scale, synthetic_example=True)
            score, truth = eval_grid(result["score_map"], mask if row["label"] == "1" else None)
            if truth is None:
                truth = np.zeros(score.shape, np.uint8)
            pixel_pairs.append((truth, score))
            ys.append(int(row["label"]))
            scores.append(float(result["score"]))
            decisions.append(policy["decision"])
            per_case.append({"category": category, "case_id": row["case_id"], "label": int(row["label"]),
                "decision": policy["decision"], "score": float(result["score"]), "image_sha256": sha256_file(ip),
                "mask_sha256": sha256_file(mp), "source": "synthetic fixture QA"})
        im = threshold_metrics(np.asarray(ys), np.asarray(scores), meta["image_threshold"]); im.pop("predictions", None)
        results.append({"category": category, "status": "COMPLETED", "synthetic_only": True,
            "fit_count": len(train), "calibration_count": len(calibration),
            "evaluation_count": len(ys), "normal_count": len(eval_normals), "defect_count": len(defect),
            "image_metrics": im, "pixel_metrics": pixel_metrics(pixel_pairs, meta["pixel_threshold"]),
            "agent_decisions": decision_metrics(np.asarray(ys), decisions),
            "bank_sha256": meta["normal_bank_sha256"], "model_changes": False})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps({"source": "REFLEX_SAMPLE_IMAGE_KIT.zip", "real_world_benchmark": False, "categories": results}, indent=2), encoding="utf-8")
    with (OUT / "per_case.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_case[0])); writer.writeheader(); writer.writerows(per_case)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
