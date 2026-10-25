"""Frozen OpenCV detector evaluation on the available official VisA splits."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

import cv2
import numpy as np

from app.agent.controller import inspect_crop, run_policy
from app.core.model import analyze, fit_normal_bank, load_bank, read_bgr, render_evidence
from reflex_bench.data import Case, eval_grid, image_case, list_images, sha256_file, split_normal, visa_cases
from reflex_bench.metrics import area_slices, decision_metrics, pixel_metrics, threshold_metrics


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("REFLEX_VISA_PREPARED", str(ROOT / "data" / "visa" / "prepared")))
OUT = ROOT / "reports" / "benchmarks"
SEED = 20261023
THUMB_LIMIT = 512


def _quantile(values: list[float], q: float) -> float | None:
    return float(np.quantile(np.asarray(values, dtype=np.float64), q)) if values else None


def _latency(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=np.float64)
    return {
        "count": int(arr.size), "mean_ms": float(arr.mean()) if arr.size else None,
        "std_ms": float(arr.std(ddof=1)) if arr.size > 1 else (0.0 if arr.size else None),
        "p50_ms": _quantile(values, 0.50), "p90_ms": _quantile(values, 0.90),
        "p95_ms": _quantile(values, 0.95), "max_ms": float(arr.max()) if arr.size else None,
    }


def _region_metrics(pairs: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    evaluated = hits = 0
    ious = []
    for truth, pred in pairs:
        if not truth.any():
            continue
        evaluated += 1
        count, cc = cv2.connectedComponents(truth.astype(np.uint8), connectivity=8)
        for cid in range(1, count):
            component = cc == cid
            intersection = int(np.sum(component & pred))
            union = int(np.sum(component | pred))
            iou = intersection / max(union, 1)
            ious.append(iou)
            hits += int(intersection > 0)
    return {"defect_image_count": evaluated, "component_count": len(ious), "component_recall_any_overlap": hits / max(len(ious), 1), "mean_component_iou": float(np.mean(ious)) if ious else None}


def _random_crop_decision(image: np.ndarray, analysis: dict, mean: np.ndarray, scale: np.ndarray, rng: random.Random) -> tuple[str, bool]:
    flags = analysis["quality"]["flags"]
    if flags:
        return "NEEDS_REVIEW", False
    if analysis["score"] <= analysis["threshold"]:
        return "PASS", False
    if not analysis["regions"]:
        return "NEEDS_REVIEW", False
    x1, y1, x2, y2 = analysis["regions"][0]["bbox_xyxy"]
    width, height = image.shape[1], image.shape[0]
    cw, ch = min(max(8, x2 - x1), width), min(max(8, y2 - y1), height)
    rx = rng.randint(0, max(width - cw, 0))
    ry = rng.randint(0, max(height - ch, 0))
    result = inspect_crop(image, [rx, ry, rx + cw, ry + ch], mean, scale, analysis["pixel_threshold"])
    return ("DEFECT_FOUND" if result["crop_score_exceeds_pixel_threshold"] else "NEEDS_REVIEW"), True


def _decision_no_crop(analysis: dict) -> str:
    if analysis["quality"]["flags"]:
        return "NEEDS_REVIEW"
    if analysis["score"] <= analysis["threshold"]:
        return "PASS"
    return "DEFECT_FOUND" if analysis["regions"] else "NEEDS_REVIEW"


def _save_gallery(category: str, records: list[dict]) -> list[str]:
    target = OUT / "galleries" / category
    target.mkdir(parents=True, exist_ok=True)
    normals = [r for r in records if r["label"] == 0]
    defects = [r for r in records if r["label"] == 1]
    normals_high = sorted(normals, key=lambda r: -r["score"])[:3]
    normals_low = sorted(normals, key=lambda r: r["score"])[:3]
    defects_high = sorted(defects, key=lambda r: -r["score"])[:3]
    defects_low = sorted(defects, key=lambda r: r["score"])[:3]
    selected = []
    seen = set()
    for row in normals_high + normals_low + defects_high + defects_low:
        if row["case_id"] not in seen:
            seen.add(row["case_id"])
            selected.append(row)
    names = []
    for i, row in enumerate(selected):
        img = read_bgr(Path(row["_image_source_path"]))
        smap = np.load(row["_score_map_source_path"])
        _, overlay, _ = render_evidence(img, smap, row["pixel_threshold"])
        mask = cv2.imread(row["_mask_source_path"], cv2.IMREAD_GRAYSCALE) if row["_mask_source_path"] else np.zeros(img.shape[:2], np.uint8)
        gt = img.copy()
        if mask is not None and np.any(mask):
            tint = np.zeros_like(gt); tint[:, :, 2] = 255
            gt[mask > 0] = cv2.addWeighted(gt[mask > 0], 0.45, tint[mask > 0], 0.55, 0)
        # Keep diagnostic thumbnails within a compact, documented maximum dimension.
        max_dim = max(img.shape[:2])
        scale = min(1.0, THUMB_LIMIT / max_dim)
        dims = (max(1, round(img.shape[1] * scale)), max(1, round(img.shape[0] * scale)))
        panels = [cv2.resize(img, dims), cv2.resize(overlay, dims), cv2.resize(gt, dims)]
        joined = np.hstack(panels)
        labeled = np.full((joined.shape[0] + 46, joined.shape[1], 3), 248, dtype=np.uint8)
        labeled[46:] = joined
        labels = ["Input image", "Anomaly evidence overlay", "Ground-truth mask"]
        for panel_index, title in enumerate(labels):
            cv2.putText(labeled, title, (panel_index * dims[0] + 12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (32, 36, 42), 1, cv2.LINE_AA)
        cv2.putText(labeled, f"{category} | {row['case_id']} | label={'defect' if row['label'] else 'normal'} | decision={row['decision_agent']}",
                    (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 76, 84), 1, cv2.LINE_AA)
        name = f"{i:02d}_{Path(row['image_path']).stem}_{row['decision_agent']}.jpg"
        cv2.imwrite(str(target / name), labeled, [cv2.IMWRITE_JPEG_QUALITY, 92])
        names.append(str((target / name).relative_to(ROOT)).replace("\\", "/"))
    return names


def run_category(category: str) -> dict:
    category_root = DATA / category
    train_paths, good_cases, bad_cases = visa_cases(category_root)
    train, calibration = split_normal(train_paths, SEED)
    model_dir = OUT / "models" / category
    meta = fit_normal_bank(train, calibration, model_dir, seed=SEED, source=f"visa:{category}")
    mean, scale, meta = load_bank(model_dir)
    cases = good_cases + bad_cases
    rng = random.Random(SEED + sum(map(ord, category)))
    records = []
    raw_scores, labels, masks_for_pixel, fractions = [], [], [], []
    no_crop, full_agent, random_agent, no_quality_gate = [], [], [], []
    agent_latency, first_pass_latency = [], []
    maps_dir = OUT / "maps" / category
    maps_dir.mkdir(parents=True, exist_ok=True)
    random_count = native_crop_count = 0
    quality_counts: dict[str, int] = {}
    for index, case in enumerate(cases):
        image, mask = image_case(case)
        started = time.perf_counter()
        result = analyze(image, mean, scale, meta)
        first_pass_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        policy = run_policy(image, result, mean, scale)
        policy_ms = (time.perf_counter() - started) * 1000
        quality_off = dict(result)
        quality_off["quality"] = dict(result["quality"], flags=[])
        quality_off_decision = run_policy(image, quality_off, mean, scale)["decision"]
        rand_decision, used_random = _random_crop_decision(image, result, mean, scale, rng)
        if used_random:
            random_count += 1
        native_crop_count += int(any(s.get("selected_tool") == "inspect_crop" for s in policy["agent_trace"]))
        no_crop_decision = _decision_no_crop(result)
        flags = result["quality"]["flags"]
        for f in flags:
            quality_counts[f] = quality_counts.get(f, 0) + 1
        score, eval_mask = eval_grid(result["score_map"], mask if case.label else None)
        # Normal images contribute a full negative pixel map. Defective masks are at the same grid.
        if case.label == 0:
            eval_mask = np.zeros(score.shape, dtype=np.uint8)
        masks_for_pixel.append((eval_mask, score))
        raw_scores.append(float(result["score"]))
        labels.append(int(case.label))
        fractions.append(float(np.mean(mask > 0)))
        no_crop.append(no_crop_decision)
        full_agent.append(policy["decision"])
        random_agent.append(rand_decision)
        no_quality_gate.append(quality_off_decision)
        agent_latency.append(policy_ms)
        first_pass_latency.append(first_pass_ms)
        map_path = maps_dir / f"{index:04d}.npy"
        np.save(map_path, result["score_map"].astype(np.float32))
        records.append({
            "category": category, "case_id": case.case_id,
            "image_path": f"VisA/prepared/{category}/test/{'bad' if case.label else 'good'}/{case.image_path.name}",
            "mask_path": f"VisA/prepared/{category}/ground_truth/bad/{case.mask_path.name}" if case.mask_path else "",
            "_image_source_path": str(case.image_path), "_mask_source_path": str(case.mask_path) if case.mask_path else "", "label": case.label,
            "image_sha256": sha256_file(case.image_path), "mask_sha256": sha256_file(case.mask_path) if case.mask_path else "",
            "score": float(result["score"]), "image_threshold": float(meta["image_threshold"]),
            "pixel_threshold": float(meta["pixel_threshold"]), "fixed_threshold_prediction": int(result["score"] > meta["image_threshold"]),
            "decision_static_no_crop": no_crop_decision, "decision_agent": policy["decision"],
            "decision_random_crop": rand_decision, "quality_flags": "|".join(flags),
            "localized_region_count": len(result["regions"]), "native_crop_used": int(any(s.get("selected_tool") == "inspect_crop" for s in policy["agent_trace"])),
            "random_crop_used": int(used_random), "first_pass_ms": first_pass_ms, "agent_ms": policy_ms,
            "anomaly_fraction": float(np.mean(mask > 0)), "score_map_path": f"reports/benchmarks/maps/{category}/{map_path.name}",
            "_score_map_source_path": str(map_path),
            "eval_grid_width": int(score.shape[1]), "eval_grid_height": int(score.shape[0]),
        })
    fixed = threshold_metrics(np.asarray(labels), np.asarray(raw_scores), float(meta["image_threshold"]))
    fixed.pop("predictions", None)
    grid_threshold = float(meta["pixel_threshold"])
    pix = pixel_metrics(masks_for_pixel, grid_threshold)
    region_pairs = [(m, s > grid_threshold) for m, s in masks_for_pixel]
    metadata = {
        "dataset": "VisA official one-class split", "category": category, "seed": SEED,
        "fit_normal_count": len(train), "calibration_normal_count": len(calibration),
        "fit_normal_membership": [{"path": f"VisA/prepared/{category}/{p.relative_to(category_root).as_posix()}", "sha256": sha256_file(p)} for p in train],
        "calibration_normal_membership": [{"path": f"VisA/prepared/{category}/{p.relative_to(category_root).as_posix()}", "sha256": sha256_file(p)} for p in calibration],
        "fit_calibration_split": "deterministic seed-shuffled 80/20 of train/good; defect/test data never used for fit or calibration",
        "normal_threshold": meta["image_threshold"], "pixel_threshold": meta["pixel_threshold"],
        "threshold_source": "normal calibration images only", "model_version": meta["model_version"],
        "normal_bank_sha256": meta["normal_bank_sha256"], "test_image_count": len(cases),
        "test_good_count": len(good_cases), "test_defect_count": len(bad_cases),
        "image_metrics": fixed, "pixel_metrics": pix, "region_metrics": _region_metrics(region_pairs),
        "area_slices": area_slices(np.asarray(labels), np.asarray(raw_scores), float(meta["image_threshold"]), np.asarray(fractions)),
        "agent_static_no_crop": decision_metrics(np.asarray(labels), no_crop),
        "agent_full_crop": decision_metrics(np.asarray(labels), full_agent),
        "agent_random_crop_matched": decision_metrics(np.asarray(labels), random_agent),
        "agent_quality_gate_off": decision_metrics(np.asarray(labels), no_quality_gate),
        "agent_ablation_counts": {"native_crop_calls": native_crop_count, "random_crop_calls": random_count,
            "quality_flag_counts": quality_counts, "extra_camera_view": "not implemented in current application; NOT RUN",
            "registration_ablation": "separate API exists; per-image agent does not invoke it; NOT RUN"},
        "latency": {"analyze_including_quality_and_features": _latency(first_pass_latency),
                    "policy_orchestration_only_excluding_analyze": _latency(agent_latency)},
        "pixel_grid": "aspect-preserving resize, maximum side 256; binary masks nearest-neighbor; scores linear",
        "model_changes_during_benchmark": False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    run_dir = OUT / category
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (run_dir / "per_case.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[k for k in records[0] if not k.startswith("_") and k != "score_map_path"], extrasaction="ignore")
        writer.writeheader(); writer.writerows(records)
    gallery = _save_gallery(category, records)
    metadata["gallery"] = gallery
    (run_dir / "metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    if len(sys.argv) > 1:
        categories = sys.argv[1:]
    else:
        categories = [p.name for p in DATA.iterdir() if p.is_dir() and (p / "train" / "good").exists()]
    results = []
    for category in categories:
        print(f"START {category}", flush=True)
        try:
            res = run_category(category)
            results.append({"category": category, "status": "COMPLETED", "metrics_file": f"reports/benchmarks/{category}/metrics.json",
                            "image": res["image_metrics"], "pixel": res["pixel_metrics"], "agent": res["agent_full_crop"], "latency": res["latency"]})
            print(f"DONE {category} image_AUROC={res['image_metrics']['auroc']} pixel_AUROC={res['pixel_metrics']['pixel_auroc']}", flush=True)
        except Exception as exc:
            results.append({"category": category, "status": "BLOCKED_OR_FAILED", "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAILED {category}: {type(exc).__name__}: {exc}", flush=True)
    (OUT / "real_visa_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
