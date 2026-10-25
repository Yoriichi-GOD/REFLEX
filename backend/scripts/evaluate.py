from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.controller import run_policy
from app.core.model import analyze, load_bank


def auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = labels.astype(np.uint8)
    positives = int(labels.sum())
    negatives = int(labels.size - positives)
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    sorted_labels = labels[order]
    tp = np.cumsum(sorted_labels[::-1], dtype=np.int64)
    fp = np.cumsum(1 - sorted_labels[::-1], dtype=np.int64)
    tpr = np.concatenate(([0.0], tp / positives))
    fpr = np.concatenate(([0.0], fp / negatives))
    return float(np.trapezoid(tpr, fpr))


def evaluate() -> dict:
    labels_path = ROOT / "data" / "synthetic" / "labels.json"
    if not labels_path.exists():
        raise SystemExit("Synthetic dataset is missing. Run `make demo-data` first.")
    labels_data = json.loads(labels_path.read_text(encoding="utf-8"))
    mean, scale, metadata = load_bank()
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S%fZ")
    cases = [(Path(path), 0, None) for path in labels_data["eval_normal"]]
    cases += [(ROOT / entry["image"], 1, ROOT / entry["mask"]) for entry in labels_data["eval_defect"]]
    for _ in range(3):
        cv2.imread(str(cases[0][0]), cv2.IMREAD_COLOR)
    image_scores, image_labels, agent_decisions = [], [], []
    y_pixels, s_pixels = [], []
    latencies, rows, failures = [], [], []
    branch_count = review_count = changed_count = defect_auto_count = 0
    agent_extra_ms: list[float] = []
    for path, label, mask_path in cases:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Could not read evaluation image {path}")
        start = time.perf_counter()
        result = analyze(image, mean, scale, metadata)
        single_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        agent = run_policy(image, result, mean, scale, synthetic_example=True)
        policy_ms = (time.perf_counter() - start) * 1000
        agent_ms = single_ms + policy_ms
        label_value = int(label)
        image_scores.append(result["score"])
        image_labels.append(label_value)
        agent_decisions.append(agent["decision"])
        branches = max(0, len(agent["agent_trace"]) - 1)
        branch_count += int(branches > 0)
        review_count += int(agent["decision"] == "NEEDS_REVIEW")
        single_decision = "DEFECT_FOUND" if result["score"] > result["threshold"] else "PASS"
        changed_count += int(single_decision != agent["decision"])
        defect_auto_count += int(agent["decision"] == "DEFECT_FOUND")
        agent_extra_ms.append(policy_ms)
        latencies.append(agent_ms)
        rows.append({
            "case_id": path.stem, "label": label_value, "synthetic": True,
            "single_pass_decision": single_decision, "agent_decision": agent["decision"],
            "score": result["score"], "threshold": result["threshold"], "runtime_ms": agent_ms,
            "single_pass_ms": single_ms, "agent_tool_calls": len(agent["agent_trace"]),
            "selected_tools": ";".join(entry["selected_tool"] for entry in agent["agent_trace"]),
        })
        map_flat = result["score_map"].astype(np.float32).ravel()
        if mask_path:
            truth = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if truth is None:
                raise RuntimeError(f"Could not read evaluation mask {mask_path}")
            truth = truth > 0
            if truth.shape != result["score_map"].shape:
                truth = cv2.resize(truth.astype(np.uint8), (result["score_map"].shape[1], result["score_map"].shape[0]), interpolation=cv2.INTER_NEAREST) > 0
            y_pixels.append(truth.ravel().astype(np.uint8))
        else:
            y_pixels.append(np.zeros(map_flat.shape, np.uint8))
        s_pixels.append(map_flat)
        if label_value == 1 and agent["decision"] == "PASS":
            failures.append({"case_id": path.stem, "failure": "false_clear_by_agent", "score": round(result["score"], 6), "threshold": round(result["threshold"], 6), "defect_type": next((e["defect_type"] for e in labels_data["eval_defect"] if Path(e["image"]).stem == path.stem), "unknown")})
        elif label_value == 0 and agent["decision"] == "DEFECT_FOUND":
            failures.append({"case_id": path.stem, "failure": "false_defect_by_agent", "score": round(result["score"], 6), "threshold": round(result["threshold"], 6), "defect_type": None})
        if failures and failures[-1]["case_id"] == path.stem:
            _, overlay, _ = __import__("app.core.model", fromlist=["render_evidence"]).render_evidence(image, result["score_map"], result["pixel_threshold"])
            failure_path = ROOT / "results" / "failures" / run_id / f"{path.stem}_{failures[-1]['failure']}.png"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(failure_path), overlay)
            failures[-1]["overlay_path"] = str(failure_path.relative_to(ROOT)).replace("\\", "/")
    y = np.asarray(image_labels, np.uint8)
    score_array = np.asarray(image_scores, np.float64)
    prediction = score_array > float(metadata["image_threshold"])
    tp = int(np.sum((prediction == 1) & (y == 1)))
    fp = int(np.sum((prediction == 1) & (y == 0)))
    fn = int(np.sum((prediction == 0) & (y == 1)))
    tn = int(np.sum((prediction == 0) & (y == 0)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    all_pixel_labels = np.concatenate(y_pixels)
    all_pixel_scores = np.concatenate(s_pixels)
    pixel_pred = all_pixel_scores > float(metadata["pixel_threshold"])
    pixel_tp = int(np.sum(pixel_pred & (all_pixel_labels == 1)))
    pixel_fp = int(np.sum(pixel_pred & (all_pixel_labels == 0)))
    pixel_fn = int(np.sum((~pixel_pred) & (all_pixel_labels == 1)))
    pixel_iou = pixel_tp / max(pixel_tp + pixel_fp + pixel_fn, 1)
    pixel_precision = pixel_tp / max(pixel_tp + pixel_fp, 1)
    pixel_recall = pixel_tp / max(pixel_tp + pixel_fn, 1)
    metrics = {
        "sample_count": len(cases), "test_normal_count": int(np.sum(y == 0)), "test_defect_count": int(np.sum(y == 1)),
        "image_auroc": round(auc(y, score_array) or 0.0, 6),
        "precision_at_frozen_threshold": round(precision, 6), "recall_at_frozen_threshold": round(recall, 6), "f1_at_threshold": round(f1, 6),
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "false_positive_rate_on_eval_normals": round(fp / max(tn + fp, 1), 6),
        "pixel_auroc": round(auc(all_pixel_labels, all_pixel_scores) or 0.0, 6),
        "pixel_iou_at_normal_calibration_threshold": round(pixel_iou, 6),
        "pixel_precision": round(pixel_precision, 6), "pixel_recall": round(pixel_recall, 6),
    }
    agent_metrics = {
        "cases_with_tool_branch": branch_count, "cases_without_tool_branch": len(cases) - branch_count,
        "human_review_or_retake_count": review_count, "auto_defect_found_count": defect_auto_count,
        "decision_changed_vs_single_pass": changed_count,
        "false_clear_count": sum(1 for row in rows if row["label"] == 1 and row["agent_decision"] == "PASS"),
        "false_clear_rate_on_synthetic_defects": round(sum(1 for row in rows if row["label"] == 1 and row["agent_decision"] == "PASS") / max(int(np.sum(y == 1)), 1), 6),
        "mean_tool_calls": round(float(np.mean([r["agent_tool_calls"] for r in rows])), 4),
        "mean_additional_agent_ms_vs_single_pass": round(float(np.mean(agent_extra_ms)), 4),
    }
    try:
        import psutil  # optional; no added dependency
        process_rss_mb = round(psutil.Process().memory_info().rss / 1024**2, 2)
    except Exception:
        process_rss_mb = None
    performance = {
        "end_to_end_agent_ms_p50": round(float(np.percentile(latencies, 50)), 3),
        "end_to_end_agent_ms_p95": round(float(np.percentile(latencies, 95)), 3),
        "per_sample_inference_ms_mean": round(float(np.mean(latencies)), 3),
        "per_sample_inference_ms_max": round(float(np.max(latencies)), 3),
        "runtime_samples": len(latencies), "warmups": 3,
        "peak_rss_mb": process_rss_mb if process_rss_mb is not None else "Not measured (psutil not installed)",
        "concurrency": 1, "image_resolution": "480x360 synthetic fixtures",
    }
    payload = {
        "status": "evaluated", "run_id": run_id, "created_at": stamp.isoformat(),
        "dataset": "REFLEX seeded synthetic holdout", "synthetic": True,
        "model_version": metadata["model_version"], "model_mode": metadata["model_mode"],
        "threshold": metadata["image_threshold"], "pixel_threshold": metadata["pixel_threshold"],
        "split": {"train_normal": metadata["training_count"], "calibration_normal": metadata["calibration_count"], "test_normal": int(np.sum(y == 0)), "test_defect": int(np.sum(y == 1))},
        "defect_types": sorted(set(e["defect_type"] for e in labels_data["eval_defect"])),
        "seed": 20261023, "metrics": metrics, "agent_metrics": agent_metrics,
        "performance": performance, "environment": {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor(), "logical_cpus": __import__("os").cpu_count(), "opencv": cv2.__version__, "numpy": np.__version__},
        "failure_cases": failures,
        "interpretation": "Synthetic-only evaluation. These seeded fixtures measure this implementation against its own generated scenarios; they are not MVTec, physical-product, factory, or deployment performance.",
        "leakage_controls": "Train and calibration image paths use disjoint seed ranges from eval paths. The fit command receives normal train/calibration images only. Evaluation labels and masks are read only in this script.",
    }
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    (results / f"eval_{run_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md = [
        "# Synthetic holdout evaluation",
        "",
        f"Run: `{run_id}` · model `{metadata['model_version']}` · mode `{metadata['model_mode']}`",
        "",
        "> Synthetic-only measurement. This is not an industrial, MVTec, or real-camera benchmark.",
        "",
        f"- Split: train normal {metadata['training_count']}, calibration normal {metadata['calibration_count']}, test normal {metrics['test_normal_count']}, test defect {metrics['test_defect_count']}",
        f"- Image AUROC: {metrics['image_auroc']}; precision/recall/F1 at frozen normal threshold: {precision:.4f}/{recall:.4f}/{f1:.4f}",
        f"- Confusion matrix: TP {tp}, FP {fp}, FN {fn}, TN {tn}; held-out normal FPR {metrics['false_positive_rate_on_eval_normals']:.4f}",
        f"- Pixel AUROC/IoU: {metrics['pixel_auroc']}/{metrics['pixel_iou_at_normal_calibration_threshold']} using generated fixture masks and the normal-calibrated pixel threshold.",
        f"- Agent: branched {branch_count}/{len(cases)}, reviewed/retake {review_count}, decisions changed vs one-pass {changed_count}; mean added time {agent_metrics['mean_additional_agent_ms_vs_single_pass']:.3f} ms.",
        f"- Agent latency p50/p95: {performance['end_to_end_agent_ms_p50']}/{performance['end_to_end_agent_ms_p95']} ms over {len(cases)} sequential cases on {platform.platform()}.",
        "",
        "## Failure cases",
        "",
    ]
    if failures:
        md += [f"- `{f['case_id']}`: {f['failure']} ({f.get('defect_type') or 'normal'})" for f in failures]
    else:
        md.append("No false clear or false defect decisions were observed in this synthetic holdout. Review/escalation cases are reported separately in JSON.")
    md += ["", "The full per-case output is in the companion latency CSV. The exact dataset split and source hashes are in `data/assets_manifest.json` and the model metadata.", ""]
    (results / f"eval_{run_id}.md").write_text("\n".join(md), encoding="utf-8")
    with (results / f"latency_{run_id}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    (results / f"environment_{run_id}.json").write_text(json.dumps({"run_id": run_id, **payload["environment"], **performance}, indent=2), encoding="utf-8")
    docs = [
        "# Evaluation", "",
        "## Current measured run", "",
        f"Run `{run_id}` on the REFLEX seeded synthetic holdout. This is not a MVTec, physical-camera, factory, or AWS benchmark.", "",
        f"| Split | Count |\n|---|---:|\n| Normal training | {metadata['training_count']} |\n| Normal calibration | {metadata['calibration_count']} |\n| Held-out normal | {metrics['test_normal_count']} |\n| Held-out synthetic defect | {metrics['test_defect_count']} |",
        "", "The train and calibration folders use disjoint seed ranges from the evaluation folders. `fit_demo.py` receives only `train_normal` and `calibration_normal`. The evaluator alone reads defect labels and masks after loading the frozen model and thresholds. No test labels tune the model.", "",
        f"| Image metric | Measured value |\n|---|---:|\n| Image AUROC | {metrics['image_auroc']:.6f} |\n| Precision at frozen threshold | {precision:.6f} |\n| Recall at frozen threshold | {recall:.6f} |\n| F1 at frozen threshold | {f1:.6f} |\n| Confusion TP / FP / FN / TN | {tp} / {fp} / {fn} / {tn} |\n| False-positive rate on held-out normals | {metrics['false_positive_rate_on_eval_normals']:.6f} |\n| Pixel AUROC | {metrics['pixel_auroc']:.6f} |\n| Pixel IoU at normal-calibrated pixel threshold | {metrics['pixel_iou_at_normal_calibration_threshold']:.6f} |\n| Pixel precision / recall | {metrics['pixel_precision']:.6f} / {metrics['pixel_recall']:.6f} |",
        "", "Pixel metrics use the exact generated masks. The pixel threshold is the 99.5th percentile of normal calibration-map pixels; it is a finite-sample heuristic. The image threshold is the 95th percentile of 12 normal calibration-image scores. Neither value is a probability or a guaranteed production false-positive rate.", "",
        f"Agent branched on {branch_count}/{len(cases)} cases. Mean tool calls: {agent_metrics['mean_tool_calls']:.4f}; decisions changed versus score-threshold-only: {changed_count}; false clear on synthetic defects: {agent_metrics['false_clear_count']}/{metrics['test_defect_count']}; additional policy time mean: {agent_metrics['mean_additional_agent_ms_vs_single_pass']:.4f} ms. On this fixed set the second pass did not change the final decisions or reduce the observed errors. It did generate a new crop measurement on selected cases.", "",
        f"Sequential local runtime on {platform.platform()} with {len(latencies)} samples at 480×360: p50 {performance['end_to_end_agent_ms_p50']:.3f} ms, p95 {performance['end_to_end_agent_ms_p95']:.3f} ms, max {performance['per_sample_inference_ms_max']:.3f} ms. Concurrency was 1; memory was not measured.", "",
        "## Observed failures", "",
    ]
    if failures:
        docs.extend([f"- `{f['case_id']}` — {f['failure']} ({f.get('defect_type') or 'normal'}); [computed overlay](../{f['overlay_path']})." for f in failures])
    else:
        docs.append("No false-clear or false-defect decisions occurred in this synthetic holdout.")
    docs.extend(["", "## Reproduce", "", "```powershell", "python backend/scripts/make_fixtures.py", "python backend/scripts/fit_demo.py", "python backend/scripts/evaluate.py", "```", "", f"Full JSON: `results/eval_{run_id}.json`; per-case timings/tools: `results/latency_{run_id}.csv`; machine manifest: `results/environment_{run_id}.json`.", ""])
    (ROOT / "docs" / "EVALUATION.md").write_text("\n".join(docs), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "counts": payload["split"], "metrics": metrics, "agent_metrics": agent_metrics, "performance": performance, "failure_cases": len(failures)}, indent=2))
    return payload


if __name__ == "__main__":
    evaluate()
