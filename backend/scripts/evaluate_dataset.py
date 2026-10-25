from __future__ import annotations

import argparse
import csv
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.controller import run_policy
from app.core.model import analyze, load_bank, render_evidence


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
DATASET_INFO = {
    "MVTec-AD-v1": {
        "display_name": "MVTec AD v1",
        "license": "CC BY-NC-SA 4.0; non-commercial use only, attribution/share-alike apply",
        "expected_source_prefix": "MVTec-AD-v1:",
        "manifest_required": False,
    },
    "VisA-1cls": {
        "display_name": "Visual Anomaly (VisA), 2022-09-22 release",
        "license": "CC BY 4.0",
        "expected_source_prefix": "VisA-1cls:",
        "manifest_required": True,
    },
}


def roc_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = np.asarray(labels, dtype=np.uint8).ravel()
    scores = np.asarray(scores, dtype=np.float64).ravel()
    positives = int(labels.sum())
    negatives = int(labels.size - positives)
    if not positives or not negatives or scores.size != labels.size:
        return None
    order = np.argsort(-scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    group_ends = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(sorted_scores) - 1]
    true_positives = np.cumsum(sorted_labels, dtype=np.int64)[group_ends]
    false_positives = group_ends + 1 - true_positives
    tpr = np.r_[0.0, true_positives / positives]
    fpr = np.r_[0.0, false_positives / negatives]
    return float(np.trapezoid(tpr, fpr))


def average_precision(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = np.asarray(labels, dtype=np.uint8).ravel()
    scores = np.asarray(scores, dtype=np.float64).ravel()
    positives = int(labels.sum())
    if not positives or scores.size != labels.size:
        return None
    order = np.argsort(-scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    group_ends = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(sorted_scores) - 1]
    true_positives = np.cumsum(sorted_labels, dtype=np.int64)[group_ends]
    false_positives = group_ends + 1 - true_positives
    precision = true_positives / np.maximum(true_positives + false_positives, 1)
    recall = true_positives / positives
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


def pixel_metrics(mask_maps: list[tuple[np.ndarray, np.ndarray]], threshold: float) -> dict:
    labels = []
    scores = []
    for mask, score_map in mask_maps:
        truth = cv2.resize(mask.astype(np.uint8), (score_map.shape[1], score_map.shape[0]), interpolation=cv2.INTER_NEAREST)
        labels.append((truth > 0).astype(np.uint8).ravel())
        scores.append(score_map.astype(np.float32).ravel())
    if not labels:
        return {"pixel_auroc": None, "pixel_average_precision": None, "pixel_samples": 0, "pixel_image_count": 0}
    y_true = np.concatenate(labels)
    y_score = np.concatenate(scores)
    predictions = y_score > float(threshold)
    tp = int(np.sum(predictions & (y_true == 1)))
    fp = int(np.sum(predictions & (y_true == 0)))
    fn = int(np.sum((~predictions) & (y_true == 1)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "pixel_auroc": roc_auc(y_true, y_score),
        "pixel_average_precision": average_precision(y_true, y_score),
        "pixel_iou_at_frozen_normal_threshold": tp / max(tp + fp + fn, 1),
        "pixel_f1_at_frozen_normal_threshold": 2 * precision * recall / max(precision + recall, 1e-12),
        "pixel_precision": precision,
        "pixel_recall": recall,
        "pixel_samples": int(y_true.size),
        "pixel_image_count": len(mask_maps),
        "pixel_metric_grid": "120x90 OpenCV feature map; masks resized with nearest-neighbor interpolation",
    }


def process_memory_mb() -> tuple[float | None, float | None]:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        try:
            psapi = ctypes.WinDLL("Psapi.dll")
            kernel32 = ctypes.WinDLL("Kernel32.dll")
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
            psapi.GetProcessMemoryInfo.restype = ctypes.c_int
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            ok = psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
            if ok:
                return counters.WorkingSetSize / (1024 * 1024), counters.PeakWorkingSetSize / (1024 * 1024)
        except (AttributeError, OSError):
            pass
        return None, None
    try:
        import resource
        peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        scale = 1024 * 1024 if platform.system() == "Darwin" else 1024
        return peak / scale, peak / scale
    except (ImportError, AttributeError, OSError):
        return None, None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a frozen normal bank on a held-out MVTec-shaped benchmark split.")
    parser.add_argument("--dataset-dir", required=True, type=Path, help="Prepared benchmark root with <class>/train and <class>/test")
    parser.add_argument("--class-name", required=True)
    parser.add_argument("--dataset-id", choices=tuple(DATASET_INFO), default="MVTec-AD-v1")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--failure-dir", type=Path, default=None, help="Optional external folder for computed error overlays; keep dataset-derived images out of the repo")
    args = parser.parse_args()
    info = DATASET_INFO[args.dataset_id]
    category = args.dataset_dir / args.class_name
    if not (category / "test" / "good").is_dir():
        raise SystemExit(f"Benchmark test split not found at {category / 'test'}")
    source_manifest = category / "dataset_manifest.json"
    source_manifest_sha256 = None
    source_manifest_data = None
    if info["manifest_required"]:
        if not source_manifest.is_file():
            raise SystemExit(f"{args.dataset_id} requires a dataset manifest from prepare_visa.py.")
        manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
        if manifest.get("dataset") != info["display_name"] or manifest.get("class_name") != args.class_name:
            raise SystemExit("The prepared dataset manifest does not match the requested benchmark class.")
        source_manifest_sha256 = sha256_file(source_manifest)
        source_manifest_data = manifest

    default_model_prefix = "mvtec" if args.dataset_id == "MVTec-AD-v1" else "visa"
    model_dir = args.model_dir or (ROOT / "data" / "models" / f"{default_model_prefix}_{args.class_name}")
    model_load_started = time.perf_counter()
    mean, scale, metadata = load_bank(model_dir)
    model_load_ms = (time.perf_counter() - model_load_started) * 1000
    expected_source = f"{info['expected_source_prefix']}{args.class_name}"
    if metadata.get("data_source") != expected_source:
        raise SystemExit(f"Selected model source {metadata.get('data_source')!r} does not match {expected_source!r}.")
    if source_manifest_sha256 and metadata.get("dataset_manifest_sha256") != source_manifest_sha256:
        raise SystemExit("The fitted model references a different prepared dataset manifest.")

    test_root = category / "test"
    cases = [(p, 0, None, "good") for p in sorted((test_root / "good").rglob("*")) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    defect_types = []
    for defect_dir in sorted(test_root.iterdir()):
        if not defect_dir.is_dir() or defect_dir.name == "good":
            continue
        defect_types.append(defect_dir.name)
        for path in sorted(defect_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            mask = category / "ground_truth" / defect_dir.name / f"{path.stem}_mask.png"
            cases.append((path, 1, mask if mask.is_file() else None, defect_dir.name))
    if not cases or not any(label for _, label, _, _ in cases):
        raise SystemExit("No labeled defect test cases were found.")

    scores: list[float] = []
    labels: list[int] = []
    pixel_pairs: list[tuple[np.ndarray, np.ndarray]] = []
    rows: list[dict] = []
    agent_decisions: list[str] = []
    agent_overhead: list[float] = []
    total_latencies: list[float] = []
    working_set_samples: list[float] = []
    peak_working_set_mb: float | None = None
    missing_masks = 0
    decode_failures = 0
    first_inference_ms: float | None = None
    for path, label, mask_path, defect_type in cases:
        case_started = time.perf_counter()
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            decode_failures += 1
            continue
        result_started = time.perf_counter()
        result = analyze(image, mean, scale, metadata)
        single_ms = (time.perf_counter() - result_started) * 1000
        if first_inference_ms is None:
            first_inference_ms = single_ms
        agent_started = time.perf_counter()
        agent = run_policy(image, result, mean, scale)
        policy_ms = (time.perf_counter() - agent_started) * 1000
        total_ms = (time.perf_counter() - case_started) * 1000
        scores.append(float(result["score"]))
        labels.append(label)
        agent_decisions.append(str(agent["decision"]))
        agent_overhead.append(policy_ms)
        total_latencies.append(total_ms)
        relative_id = path.relative_to(category).as_posix()
        row = {
            "case_id": relative_id,
            "image_sha256": sha256_file(path),
            "source_width": int(image.shape[1]),
            "source_height": int(image.shape[0]),
            "label": label,
            "defect_type": defect_type,
            "score": float(result["score"]),
            "threshold": float(result["threshold"]),
            "single_pass_inference_ms": single_ms,
            "agent_extra_ms": policy_ms,
            "end_to_end_load_score_policy_ms": total_ms,
            "agent_decision": agent["decision"],
            "agent_tools": ";".join(t["selected_tool"] for t in agent["agent_trace"]),
            "mask_sha256": None,
        }
        if label == 0:
            pixel_pairs.append((np.zeros(image.shape[:2], dtype=np.uint8), result["small_score_map"]))
        elif mask_path is None:
            missing_masks += 1
        else:
            truth = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if truth is None:
                missing_masks += 1
            else:
                pixel_pairs.append((truth, result["small_score_map"]))
                row["mask_sha256"] = sha256_file(mask_path)
        working_set_mb, observed_peak_mb = process_memory_mb()
        if working_set_mb is not None:
            working_set_samples.append(working_set_mb)
        if observed_peak_mb is not None:
            peak_working_set_mb = max(peak_working_set_mb or 0.0, observed_peak_mb)
        rows.append(row)

    y = np.asarray(labels, np.uint8)
    score_values = np.asarray(scores, np.float64)
    if y.size == 0 or not np.any(y == 1) or not np.any(y == 0):
        raise SystemExit("No complete mix of good and defective images could be decoded.")
    frozen_threshold = float(metadata["image_threshold"])
    baseline_predictions = score_values > frozen_threshold
    tp = int(np.sum(baseline_predictions & (y == 1)))
    fp = int(np.sum(baseline_predictions & (y == 0)))
    fn = int(np.sum((~baseline_predictions) & (y == 1)))
    tn = int(np.sum((~baseline_predictions) & (y == 0)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    pixel = pixel_metrics(pixel_pairs, float(metadata["pixel_threshold"]))
    agent_predictions = [1 if decision == "DEFECT_FOUND" else 0 if decision == "PASS" else None for decision in agent_decisions]
    resolved = [(int(label), pred) for label, pred in zip(y, agent_predictions) if pred is not None]
    agent_errors = sum(label != pred for label, pred in resolved)
    baseline_errors = int(np.sum(baseline_predictions != y))
    corrected_by_agent = sum(baseline_predictions[i] != y[i] and agent_predictions[i] == int(y[i]) for i in range(len(y)) if agent_predictions[i] is not None)
    regressed_by_agent = sum(baseline_predictions[i] == y[i] and agent_predictions[i] != int(y[i]) for i in range(len(y)) if agent_predictions[i] is not None)
    decision_changes = sum(pred is None or pred != int(baseline_predictions[i]) for i, pred in enumerate(agent_predictions))
    agent_metrics = {
        "cases_with_tool_branch": sum(len(row["agent_tools"].split(";")) > 1 for row in rows),
        "cases_without_tool_branch": sum(len(row["agent_tools"].split(";")) <= 1 for row in rows),
        "human_capture_or_review_requests": sum(pred is None for pred in agent_predictions),
        "single_pass_errors": baseline_errors,
        "agent_errors_on_resolved_cases": agent_errors,
        "agent_resolved_case_count": len(resolved),
        "agent_error_rate_on_resolved_cases": agent_errors / max(len(resolved), 1),
        "cases_corrected_by_agent": int(corrected_by_agent),
        "cases_regressed_by_agent": int(regressed_by_agent),
        "agent_decision_changes_including_escalations": int(decision_changes),
        "false_clear_count": int(sum(label == 1 and decision == "PASS" for label, decision in zip(y, agent_decisions))),
        "mean_additional_agent_ms": float(np.mean(agent_overhead)),
        "tool_call_distribution": {
            tool: sum(tool in row["agent_tools"].split(";") for row in rows)
            for tool in sorted({tool for row in rows for tool in row["agent_tools"].split(";")})
        },
    }
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S%fZ")
    dataset_key = args.dataset_id.lower().replace("-", "_")
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    failure_cases = []
    if args.failure_dir:
        args.failure_dir.mkdir(parents=True, exist_ok=True)
        for index, row in enumerate(rows):
            baseline_wrong = bool(baseline_predictions[index] != y[index])
            agent_pred = agent_predictions[index]
            agent_wrong = agent_pred is not None and agent_pred != int(y[index])
            if not baseline_wrong and not agent_wrong:
                continue
            case_path = category / Path(row["case_id"])
            image = cv2.imread(str(case_path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            result = analyze(image, mean, scale, metadata)
            _, overlay, _ = render_evidence(image, result["score_map"], float(metadata["pixel_threshold"]))
            outcome = "baseline_error" if baseline_wrong else "agent_error"
            output = args.failure_dir / f"{Path(row['case_id']).stem}_{outcome}.png"
            if cv2.imwrite(str(output), overlay):
                failure_cases.append({"case_id": row["case_id"], "kind": outcome, "file": str(output)})

    metrics = {
        "sample_count": int(y.size),
        "test_good_count": int(np.sum(y == 0)),
        "test_defect_count": int(np.sum(y == 1)),
        "decode_failures": decode_failures,
        "image_auroc": roc_auc(y, score_values),
        "precision_at_frozen_threshold": precision,
        "recall_at_frozen_threshold": recall,
        "f1_at_frozen_threshold": f1,
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "false_positive_rate_on_test_good": fp / max(fp + tn, 1),
        "missing_or_unreadable_defect_masks": missing_masks,
        **pixel,
    }
    warm_latencies = total_latencies[1:] if len(total_latencies) > 1 else []
    current_working_set_mb, observed_peak_mb = process_memory_mb()
    if observed_peak_mb is not None:
        peak_working_set_mb = max(peak_working_set_mb or 0.0, observed_peak_mb)
    performance = {
        "first_single_pass_inference_ms": first_inference_ms,
        "warm_end_to_end_p50_ms_excluding_first_case": float(np.percentile(warm_latencies, 50)) if warm_latencies else None,
        "warm_end_to_end_p95_ms_excluding_first_case": float(np.percentile(warm_latencies, 95)) if warm_latencies else None,
        "end_to_end_p50_ms": float(np.percentile(total_latencies, 50)) if total_latencies else None,
        "end_to_end_p95_ms": float(np.percentile(total_latencies, 95)) if total_latencies else None,
        "runtime_samples": len(total_latencies),
        "image_resolution": "per-file source dimensions",
        "model_load_ms": model_load_ms,
        "mean_process_working_set_mb": float(np.mean(working_set_samples)) if working_set_samples else current_working_set_mb,
        "max_process_working_set_mb": peak_working_set_mb if peak_working_set_mb is not None else (max(working_set_samples) if working_set_samples else None),
        "memory_scope": "Whole evaluator process working set; not isolated per-request allocation.",
    }
    payload = {
        "status": "evaluated",
        "run_id": run_id,
        "created_at": stamp.isoformat(),
        "dataset": info["display_name"],
        "dataset_id": args.dataset_id,
        "dataset_manifest_sha256": source_manifest_sha256,
        "dataset_provenance": {
            "dataset_source": source_manifest_data.get("dataset_source"),
            "archive_source": source_manifest_data.get("archive_source"),
            "archive_sha256": source_manifest_data.get("archive_sha256"),
            "complete_archive_sha256_verified": source_manifest_data.get("archive_sha256") is not None,
            "official_split_source": source_manifest_data.get("split_source"),
            "official_split_sha256": source_manifest_data.get("split_file_sha256"),
            "prepared_class_file_count": len(source_manifest_data.get("images", [])),
        } if source_manifest_data else None,
        "synthetic": False,
        "class_name": args.class_name,
        "license": info["license"],
        "model_version": metadata["model_version"],
        "model_mode": metadata["model_mode"],
        "normal_bank_sha256": metadata["normal_bank_sha256"],
        "threshold": frozen_threshold,
        "pixel_threshold": float(metadata["pixel_threshold"]),
        "split": {
            "train_normal": metadata["training_count"],
            "calibration_normal": metadata["calibration_count"],
            "test_good": metrics["test_good_count"],
            "test_defect": metrics["test_defect_count"],
            "calibration_seed": metadata["calibration_seed"],
            "training_sha256": metadata["training_sha256"],
            "calibration_sha256": metadata["calibration_sha256"],
        },
        "defect_types": defect_types,
        "metrics": metrics,
        "agent_metrics": agent_metrics,
        "performance": performance,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor() or "Not reported by platform",
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "opencv": cv2.__version__,
            "numpy": np.__version__,
        },
        "leakage_controls": "The normal bank and threshold were loaded before any test labels or masks were read. Fit/calibration hashes are recorded in the model metadata; test labels and masks are evaluation-only.",
        "pixel_metric_interpretation": "Pixel metrics are computed on the model's 120x90 feature grid with ground-truth masks resized by nearest neighbor. Good test images contribute all-zero masks. This measures coarse localization, not source-resolution segmentation.",
        "failure_examples": failure_cases,
        "interpretation": "Dataset-specific research benchmark results do not establish performance on factory captures or production lines.",
        "cases": rows,
    }
    prefix = f"{dataset_key}_{args.class_name}_{run_id}"
    (results / f"eval_{prefix}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (results / f"eval_{prefix}.md").write_text(
        f"# {info['display_name']} evaluation — {args.class_name}\n\n"
        f"License: {info['license']}. Synthetic: false.\n\n"
        f"- Split: train normal {metadata['training_count']}, calibration normal {metadata['calibration_count']}, test good {metrics['test_good_count']}, test defect {metrics['test_defect_count']}.\n"
        f"- Image AUROC: {metrics['image_auroc']} · F1 at frozen threshold: {f1:.4f}.\n"
        f"- Confusion: TP {tp}, FP {fp}, FN {fn}, TN {tn}; held-out normal FPR {metrics['false_positive_rate_on_test_good']:.4f}.\n"
        f"- Pixel AUROC/AP: {metrics.get('pixel_auroc')} / {metrics.get('pixel_average_precision')}; feature-grid IoU {metrics.get('pixel_iou_at_frozen_normal_threshold')}.\n"
        f"- Pixel evaluation included {pixel.get('pixel_image_count', 0)} images at the 120x90 score grid; missing/unreadable defect masks: {missing_masks}.\n"
        f"- Agent: single-pass errors {baseline_errors}; resolved agent errors {agent_errors}/{len(resolved)}; corrected/regressed {corrected_by_agent}/{regressed_by_agent}; review/capture requests {agent_metrics['human_capture_or_review_requests']}.\n"
        f"- End-to-end p50/p95: {performance['end_to_end_p50_ms']} / {performance['end_to_end_p95_ms']} ms over {len(total_latencies)} cases; mean/max process working set {performance['mean_process_working_set_mb']} / {performance['max_process_working_set_mb']} MiB.\n"
        f"- Model bank SHA256: {metadata['normal_bank_sha256']}; dataset manifest SHA256: {source_manifest_sha256 or 'Not supplied'}.\n"
        "\nThresholds were frozen from normal-only calibration data before test labels/masks were read. Pixel metrics use the model grid and include zero masks for normal test images. These results do not establish production performance.\n",
        encoding="utf-8",
    )
    with (results / f"latency_{prefix}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (results / f"environment_{prefix}.json").write_text(json.dumps(payload["environment"] | {"performance": performance}, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "dataset": args.dataset_id, "class_name": args.class_name, "metrics": metrics, "agent_metrics": agent_metrics, "performance": performance, "results_dir": str(results)}, indent=2))


if __name__ == "__main__":
    main()
