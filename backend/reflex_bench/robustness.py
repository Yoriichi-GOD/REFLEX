"""Fixed-threshold robustness evaluation on derived real VisA test images."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import time

import cv2
import numpy as np

from app.agent.controller import run_policy
from app.core.image_io import ImageInputError, decode_image
from app.core.model import analyze, load_bank
from reflex_bench.data import eval_grid, image_case, visa_cases
from reflex_bench.metrics import decision_metrics, pixel_metrics, threshold_metrics

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("REFLEX_VISA_PREPARED", str(ROOT / "data" / "visa" / "prepared")))
BENCH = ROOT / "reports" / "benchmarks"
OUT = ROOT / "reports" / "robustness"
SEED = 20261023


def _variants(image: np.ndarray, mask: np.ndarray, seed: int) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    h, w = image.shape[:2]
    rng = np.random.default_rng(seed)
    blurred = cv2.GaussianBlur(image, (5, 5), 1.2)
    noisy = np.clip(image.astype(np.float32) + rng.normal(0.0, 12.0, image.shape), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 35])
    if not ok:
        raise RuntimeError("JPEG robustness transform failed to encode")
    jpeg = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    brighten = np.clip(image.astype(np.float32) * 0.78 + 30.0, 0, 255).astype(np.uint8)
    contrast = np.clip((image.astype(np.float32) - 127.5) * 1.25 + 127.5, 0, 255).astype(np.uint8)
    angle = 7.0
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    rotated_mask = cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    small_w, small_h = max(1, round(w * 0.55)), max(1, round(h * 0.55))
    down_up = cv2.resize(cv2.resize(image, (small_w, small_h), interpolation=cv2.INTER_AREA), (w, h), interpolation=cv2.INTER_CUBIC)
    occluded = image.copy()
    ow, oh = max(8, round(w * 0.20)), max(8, round(h * 0.20))
    x, y = (w - ow) // 2, (h - oh) // 2
    fill = np.median(image.reshape(-1, 3), axis=0).astype(np.uint8)
    occluded[y:y + oh, x:x + ow] = fill
    defect_small = image.copy()
    defect_small_mask = mask.copy()
    if np.any(mask):
        ys, xs = np.where(mask > 0)
        x1, x2, y1, y2 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
        defect_patch = image[y1:y2, x1:x2]
        defect_mask = mask[y1:y2, x1:x2]
        clean = cv2.inpaint(image, (mask > 0).astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
        nw, nh = max(1, round(defect_patch.shape[1] * 0.5)), max(1, round(defect_patch.shape[0] * 0.5))
        scaled_patch = cv2.resize(defect_patch, (nw, nh), interpolation=cv2.INTER_AREA)
        scaled_mask = cv2.resize(defect_mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        px1, py1 = max(0, cx - nw // 2), max(0, cy - nh // 2)
        px2, py2 = min(w, px1 + nw), min(h, py1 + nh)
        scaled_patch = scaled_patch[:py2 - py1, :px2 - px1]
        scaled_mask = scaled_mask[:py2 - py1, :px2 - px1]
        defect_small = clean.copy()
        roi = defect_small[py1:py2, px1:px2]
        roi[scaled_mask > 0] = scaled_patch[scaled_mask > 0]
        defect_small_mask = np.zeros_like(mask)
        defect_small_mask[py1:py2, px1:px2] = scaled_mask
    return {"blur_5x5_sigma1_2": (blurred, mask), "gaussian_noise_sigma12": (noisy, mask),
            "jpeg_quality35": (jpeg, mask), "brightness_0_78_plus30": (brighten, mask),
            "contrast_1_25": (contrast, mask), "rotation_7deg": (rotated, rotated_mask),
            "resize_0_55_down_up": (down_up, mask), "defect_downsize_0_5": (defect_small, defect_small_mask),
            "center_occlusion_20pct": (occluded, mask)}


def _challenge_samples(image: np.ndarray) -> dict[str, np.ndarray]:
    h, w = image.shape[:2]
    black = np.zeros_like(image)
    white = np.full_like(image, 255)
    yy, xx = np.indices((h, w))
    tile = max(4, min(h, w) // 24)
    checker = (((xx // tile + yy // tile) % 2) * 255).astype(np.uint8)
    checker = cv2.cvtColor(checker, cv2.COLOR_GRAY2BGR)
    text = image.copy()
    cv2.putText(text, "REFLEX OOD QA", (max(8, w // 30), max(40, h // 8)), cv2.FONT_HERSHEY_SIMPLEX, max(1, w / 1200), (0, 0, 255), 3)
    left = cv2.resize(image, (w // 2, h))
    right = cv2.resize(np.flip(image, axis=1).copy(), (w - w // 2, h))
    stitched = np.hstack((left, right))
    return {"all_black": black, "all_white": white, "checkerboard": checker, "text_overlay_ood": text, "stitched_view": stitched}


def main() -> None:
    categories = ["candle", "cashew"]
    summary = []
    case_rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    for category_index, category in enumerate(categories):
        train, good, bad = visa_cases(DATA / category)
        mean, scale, meta = load_bank(BENCH / "models" / category)
        cases = good + bad
        families: dict[str, dict] = {}
        model_for_family = {name: (mean, scale, meta) for name in []}
        score_rows = {name: {"labels": [], "scores": [], "pairs": [], "decisions": [], "latencies": []}
                      for name in ("canonical_replay", "blur_5x5_sigma1_2", "gaussian_noise_sigma12", "jpeg_quality35",
                                   "brightness_0_78_plus30", "contrast_1_25", "rotation_7deg", "resize_0_55_down_up",
                                   "defect_downsize_0_5", "center_occlusion_20pct")}
        other = "cashew" if category == "candle" else "candle"
        other_mean, other_scale, other_meta = load_bank(BENCH / "models" / other)
        score_rows["wrong_category_bank"] = {"labels": [], "scores": [], "pairs": [], "decisions": [], "latencies": []}
        challenge_records = []
        for index, case in enumerate(cases):
            image, mask = image_case(case)
            derived = {"canonical_replay": (image, mask), **_variants(image, mask, SEED + index)}
            for family, (variant, truth) in derived.items():
                started = time.perf_counter()
                result = analyze(variant, mean, scale, meta)
                elapsed = (time.perf_counter() - started) * 1000
                grid_score, grid_truth = eval_grid(result["score_map"], truth if case.label else None)
                if grid_truth is None:
                    grid_truth = np.zeros(grid_score.shape, dtype=np.uint8)
                row = score_rows[family]
                row["labels"].append(case.label)
                row["scores"].append(float(result["score"]))
                row["pairs"].append((grid_truth, grid_score))
                row["decisions"].append(run_policy(variant, result, mean, scale)["decision"])
                row["latencies"].append(elapsed)
                case_rows.append({"category": category, "case_id": case.case_id, "family": family, "label": case.label,
                                  "score": float(result["score"]), "threshold": float(meta["image_threshold"]),
                                  "prediction": int(result["score"] > meta["image_threshold"]), "quality_flags": "|".join(result["quality"]["flags"])})
            started = time.perf_counter()
            wrong_result = analyze(image, other_mean, other_scale, other_meta)
            wrong_ms = (time.perf_counter() - started) * 1000
            wr = score_rows["wrong_category_bank"]
            grid_score, grid_truth = eval_grid(wrong_result["score_map"], mask if case.label else None)
            if grid_truth is None:
                grid_truth = np.zeros(grid_score.shape, dtype=np.uint8)
            wr["labels"].append(case.label); wr["scores"].append(float(wrong_result["score"]))
            wr["pairs"].append((grid_truth, grid_score)); wr["decisions"].append(run_policy(image, wrong_result, other_mean, other_scale)["decision"])
            wr["latencies"].append(wrong_ms)
            if index == 0:
                for name, sample in _challenge_samples(image).items():
                    try:
                        challenged = analyze(sample, mean, scale, meta)
                        policy = run_policy(sample, challenged, mean, scale)
                        challenge_records.append({"category": category, "challenge": name, "status": "DECODED_AND_INSPECTED",
                            "score": float(challenged["score"]), "quality_flags": challenged["quality"]["flags"],
                            "decision": policy["decision"], "requested_new_capture": any(t.get("selected_tool") == "request_new_capture" for t in policy["agent_trace"])})
                    except Exception as exc:
                        challenge_records.append({"category": category, "challenge": name, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
                try:
                    decode_image(b"REFLEX-corrupt-image-payload")
                    challenge_records.append({"category": category, "challenge": "corrupt_bytes", "status": "UNEXPECTEDLY_ACCEPTED"})
                except ImageInputError as exc:
                    challenge_records.append({"category": category, "challenge": "corrupt_bytes", "status": "REJECTED_INVALID_FORMAT", "error_code": exc.code})
        cat_metrics = []
        for family, data in score_rows.items():
            labels = np.asarray(data["labels"], dtype=np.uint8)
            score = np.asarray(data["scores"], dtype=np.float64)
            threshold_meta = other_meta if family == "wrong_category_bank" else meta
            image_result = threshold_metrics(labels, score, float(threshold_meta["image_threshold"]))
            image_result.pop("predictions", None)
            metric = {"category": category, "family": family, "n": len(labels), "image": image_result,
                      "pixel": pixel_metrics(data["pairs"], float(threshold_meta["pixel_threshold"])),
                      "agent_decisions": decision_metrics(labels, data["decisions"]),
                      "latency_ms": {"mean": float(np.mean(data["latencies"])) if data["latencies"] else None,
                                     "p95": float(np.quantile(data["latencies"], .95)) if data["latencies"] else None}}
            cat_metrics.append(metric)
        summary.append({"category": category, "source": "VisA test images with deterministic derived perturbations; not independent captures",
                        "thresholds": "unchanged normal-calibration thresholds; no re-fit per perturbation",
                        "families": cat_metrics, "challenge_input_qa": challenge_records})
    (OUT / "metrics.json").write_text(json.dumps({"model_changes": False, "canonical_scores_not_replaced": True, "categories": summary}, indent=2), encoding="utf-8")
    with (OUT / "per_case.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(case_rows[0])); writer.writeheader(); writer.writerows(case_rows)
    print(json.dumps({"categories": [{"category": x["category"], "families": [{"family": z["family"], "n": z["n"], "auroc": z["image"]["auroc"], "pixel_auroc": z["pixel"]["pixel_auroc"]} for z in x["families"]], "challenge_input_qa": x["challenge_input_qa"]} for x in summary]}, indent=2))


if __name__ == "__main__":
    main()
