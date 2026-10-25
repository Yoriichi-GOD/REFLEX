"""Matched replay-policy evaluation. Synthetic software results are never real data.

Ground truth is opened after all runtime predictions have been persisted. The
runtime receives video bytes, recipe, calibration and declared start context.
No scenario name, expected status, error label or timing reaches the engine.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import platform
import statistics
import subprocess
import time
from typing import Any, Callable

import cv2
import numpy as np

from .fixtures import SOURCE, sha256

POLICIES = ("single", "random", "agent")
STATUSES = ("PASS", "HOLD_FOR_REVIEW", "REJECT_RECOMMENDATION", "ERROR")
ERRORS = ("WRONG_COMPONENT_CLASS", "WRONG_PLACEMENT", "ORDER_VIOLATION", "MISSING_COMPONENT", "UNRECOGNIZED_COMPONENT")
QUAD = [[0., 0.], [1., 0.], [1., 1.], [0., 1.]]


def _plain(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _revision(path: Path) -> str | None:
    try:
        value = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return value.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _source_snapshot(recipe: Any) -> dict[str, Any]:
    # API/store/UI workers may continue unrelated work; freeze only the exact
    # detector, recipe, generator and evaluator used for these measurements.
    names = ("recipe.py", "vision.py", "engine.py", "fixtures.py", "benchmark.py")
    return {"module_sha256": {name: sha256(Path(__file__).parent / name) for name in names}, "recipe": _plain(recipe)}


def _wilson(k: int, n: int) -> list[float] | None:
    if not n:
        return None
    z = 1.959963984540054
    p, d = k / n, 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    delta = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5) / d
    return [max(0., center - delta), min(1., center + delta)]


def _ratio(k: int, n: int) -> float | None:
    return k / n if n else None


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "f1": _ratio(2 * tp, 2 * tp + fp + fn), "recall_wilson95": _wilson(tp, tp + fn)}


def _findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Structured matching events and supported final checkpoint decisions.

    A final-decision-only error is timed at the last analyzed frame, not an
    invented earlier onset. Final checkpoint detections are disclosed separately.
    """
    observations = {o["observation_id"]: o for o in result.get("observations", [])}
    evidence = {e["id"]: e for e in result.get("evidence", [])}

    def valid_ids(ids):
        return [i for i in ids if i in observations or i in evidence]

    findings = []
    for event in result.get("events", []):
        reason = event.get("reason_code")
        if reason in ERRORS:
            ids = valid_ids(event.get("evidence_ids", []))
            findings.append({"reason_code": reason, "video_ms": event.get("source_timestamp_ms", event.get("observed_at_ms")), "evidence_ids": ids, "kind": "event"})
    decision = result.get("decision", {})
    final_ms = max((e.get("source_timestamp_ms", 0) for e in evidence.values()), default=None)
    for reason in decision.get("reason_codes", []):
        if reason in ERRORS and not any(f["reason_code"] == reason for f in findings):
            findings.append({"reason_code": reason, "video_ms": final_ms,
                             "evidence_ids": valid_ids(decision.get("supporting_observation_ids", [])), "kind": "final_checkpoint_decision"})
    return findings


def evaluate(predictions: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate only persisted predictions. Preserve all misses and runtime errors."""
    rows = []
    for prediction in predictions:
        label = labels[prediction["clip_id"]]
        result = prediction["result"]
        findings = _findings(result)
        supported = [f for f in findings if f["evidence_ids"] and isinstance(f["video_ms"], (int, float))]
        error = label.get("error_type")
        observable = label.get("error_observable", True)
        matching = [f for f in supported if f["reason_code"] == error]
        first = min((f["video_ms"] for f in matching), default=None)
        onset, boundary = label.get("error_visible_from_ms"), label.get("last_safe_decision_ms")
        end = label.get("error_end_ms")
        # Alerts after a transient issue has ended do not count as timely detection.
        timely = first is not None and (onset is None or first >= onset) and (end is None or first < end)
        status = prediction["predicted_status"]
        expected = label["expected_status"]
        processing = result.get("processing", {})
        rows.append({
            "clip_id": prediction["clip_id"], "policy": prediction["policy"], "asset_sha256": prediction["asset_sha256"],
            "source": SOURCE, "scenario": label["scenario"], "expected_status": expected,
            "predicted_status": status, "status_correct": status == expected,
            "expected_error_type": error, "error_observable": observable,
            "expected_error_clip": bool(error and observable),
            "supported_error_types": sorted({f["reason_code"] for f in supported}),
            "supported_matching_error": bool(matching), "timely_matching_error": timely,
            "matching_event_only": any(f["reason_code"] == error and f["kind"] == "event" for f in supported),
            "first_supported_matching_alert_video_ms": first,
            "error_visible_from_ms": onset, "error_end_ms": end, "last_safe_decision_ms": boundary,
            "onset_error_ms": first - onset if first is not None and onset is not None else None,
            "lead_time_ms": boundary - first if first is not None and boundary is not None else None,
            "early_matching_alert": bool(first is not None and onset is not None and first < onset),
            "false_clear": expected != "PASS" and status == "PASS",
            "normal_false_hold": expected == "PASS" and not error and status == "HOLD_FOR_REVIEW",
            "normal_false_reject": expected == "PASS" and not error and status == "REJECT_RECOMMENDATION",
            "processing_latency_ms": prediction["processing_latency_ms"],
            "extra_inspections": processing.get("extra_inspections"),
            "extra_frame_budget": processing.get("extra_frame_budget"),
            "analyzed_frames": processing.get("analyzed_frames"),
            "decoded_frames": processing.get("decoded_frames"),
            "duration_ms": label["frame_count"] / label["fps_observed"] * 1000,
            "result_path": prediction["result_path"], "runtime_failure": prediction.get("runtime_failure"),
        })
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = {}
    for policy in POLICIES:
        group = [r for r in rows if r["policy"] == policy]
        matrix = {s: {t: 0 for t in STATUSES} for s in STATUSES[:-1]}
        for row in group:
            matrix[row["expected_status"]][row["predicted_status"]] += 1
        classes = {}
        for error in ERRORS:
            positive = [r for r in group if r["expected_error_type"] == error and r["error_observable"]]
            tp = sum(r["timely_matching_error"] for r in positive)
            fp = sum(error in r["supported_error_types"] for r in group if r["expected_error_type"] != error or not r["error_observable"])
            classes[error] = {"positive_clips": len(positive), **_prf(tp, fp, len(positive) - tp)}
        positives = [r for r in group if r["expected_error_clip"]]
        tp = sum(r["timely_matching_error"] for r in positives)
        # Binary clip detection: any spurious supported error on a negative clip.
        fp = sum(bool(r["supported_error_types"]) for r in group if not r["expected_error_clip"])
        normal = [r for r in group if r["expected_status"] == "PASS" and not r["expected_error_type"]]
        normal_hours = sum(r["duration_ms"] for r in normal) / 3_600_000
        good = [r for r in group if not r["runtime_failure"]]
        latency = [r["processing_latency_ms"] for r in good]
        action_counts = [r["extra_inspections"] for r in good if r["extra_inspections"] is not None]
        onset_values = [r["onset_error_ms"] for r in positives if r["timely_matching_error"] and r["onset_error_ms"] is not None]
        lead_values = [r["lead_time_ms"] for r in positives if r["timely_matching_error"] and r["lead_time_ms"] is not None]
        summaries[policy] = {
            "n_clips": len(group), "runtime_failure_clips": sum(bool(r["runtime_failure"]) for r in group),
            "final_status_confusion": matrix,
            "final_status_correct": sum(r["status_correct"] for r in group),
            "final_status_accuracy": _ratio(sum(r["status_correct"] for r in group), len(group)),
            "false_clear_clips": sum(r["false_clear"] for r in group),
            "clip_level_error_detection": {"positive_clips": len(positives), **_prf(tp, fp, len(positives) - tp)},
            "per_error_type": classes,
            "normal_clips": len(normal), "normal_video_hours": normal_hours,
            "normal_false_hold_clips": sum(r["normal_false_hold"] for r in normal),
            "normal_false_reject_clips": sum(r["normal_false_reject"] for r in normal),
            "normal_final_false_holds_per_video_hour": _ratio(sum(r["normal_false_hold"] for r in normal), normal_hours),
            "processing_latency_ms": {"p50": float(np.percentile(latency, 50)) if latency else None, "p95": float(np.percentile(latency, 95)) if latency else None},
            "mean_extra_inspections": statistics.mean(action_counts) if action_counts else None,
            "onset_error_ms": {"n_timely_matching_with_onset": len(onset_values), "median": statistics.median(onset_values) if onset_values else None},
            "lead_time_ms": {"n_timely_matching_with_boundary": len(lead_values), "median": statistics.median(lead_values) if lead_values else None,
                             "missed_boundary_cases": sum(r["last_safe_decision_ms"] is not None and not r["timely_matching_error"] for r in positives)},
            "early_matching_alert_clips": sum(r["early_matching_alert"] for r in group),
        }
    return summaries


def _write_gallery(output: Path, predictions: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    folder = output / "failure_gallery"
    folder.mkdir(exist_ok=True)
    cards = []
    for pred, row in zip(predictions, rows):
        result = pred["result"]
        evidence = result.get("evidence", [])
        frames = evidence[-1:]  # Actual last inference overlay, not regenerated GT.
        matching = [f for f in _findings(result) if f["reason_code"] == row["expected_error_type"] and f["evidence_ids"]]
        if matching:
            time_ms = min(f["video_ms"] for f in matching if f["video_ms"] is not None)
            matched_frame = min(evidence, key=lambda e: abs(e["source_timestamp_ms"] - time_ms)) if evidence else None
            if matched_frame and matched_frame not in frames:
                frames = [matched_frame, *frames]
        image_html = ""
        for entry in frames:
            overlay = entry.get("benchmark_overlay")
            if overlay:
                rel = Path(overlay).relative_to(output).as_posix()
                image_html += f'<figure><img src="../{html.escape(rel)}" width="640"><figcaption>Actual inference overlay at {entry["source_timestamp_ms"]} ms</figcaption></figure>'
        failed = not row["status_correct"] or (row["expected_error_clip"] and not row["timely_matching_error"]) or row["early_matching_alert"]
        cards.append(f'<article class="{"failure" if failed else "success"}"><h2>{html.escape(row["clip_id"])} · {row["policy"]}</h2><p>{"FAILURE / LIMITATION" if failed else "MATCHED FINAL STATUS"}</p>{image_html}<pre>{html.escape(json.dumps(row, indent=2))}</pre></article>')
    (folder / "index.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>REFLEX synthetic procedure inference gallery</title><style>body{font:16px Arial;background:#101927;color:#eee;margin:30px}article{border:1px solid #477;padding:18px;margin-bottom:20px}article.failure{border-color:#f96}pre{white-space:pre-wrap}img{max-width:100%}</style><h1>SYNTHETIC SOFTWARE TEST · actual inference</h1><p>All held-out clips and policies retained. Overlays were saved directly by the runtime callback before evaluation labels were opened. This is not filmed human or industrial performance.</p>' + ''.join(cards) + '</html>', encoding="utf-8")


def _confusion_image(path: Path, summaries: dict[str, Any]) -> None:
    canvas = np.full((380, 1080, 3), 250, np.uint8)
    short = {"PASS": "PASS", "HOLD_FOR_REVIEW": "HOLD", "REJECT_RECOMMENDATION": "REJECT", "ERROR": "ERROR"}
    cv2.putText(canvas, "SYNTHETIC SOFTWARE TEST | actual final-status confusion", (20, 28), cv2.FONT_HERSHEY_SIMPLEX, .65, (20, 20, 20), 2)
    for col, policy in enumerate(POLICIES):
        left = col * 360 + 10
        cv2.putText(canvas, policy.upper(), (left + 100, 65), cv2.FONT_HERSHEY_SIMPLEX, .6, (30, 30, 30), 2)
        for j, predicted in enumerate(STATUSES):
            cv2.putText(canvas, short[predicted], (left + 85 + j * 62, 105), cv2.FONT_HERSHEY_SIMPLEX, .33, (30, 30, 30), 1)
        for i, expected in enumerate(STATUSES[:-1]):
            y = 130 + i * 60
            cv2.putText(canvas, short[expected], (left + 2, y + 28), cv2.FONT_HERSHEY_SIMPLEX, .35, (30, 30, 30), 1)
            for j, predicted in enumerate(STATUSES):
                x = left + 80 + j * 62
                cv2.rectangle(canvas, (x, y), (x + 60, y + 53), (225, 236, 225) if expected == predicted else (236, 227, 217), -1)
                cv2.putText(canvas, str(summaries[policy]["final_status_confusion"][expected][predicted]), (x + 25, y + 32), cv2.FONT_HERSHEY_SIMPLEX, .55, (20, 20, 20), 1)
    cv2.putText(canvas, "Rows = expected; columns = actual. Counts are clips, not independent industrial trials.", (20, 357), cv2.FONT_HERSHEY_SIMPLEX, .48, (30, 30, 30), 1)
    if not cv2.imwrite(str(path), canvas):
        raise RuntimeError("Could not write confusion image")


def run(fixtures_root: str | Path, output: str | Path, *, split: str = "test", analyzer: Callable[..., Any] | None = None, recipe: Any = None) -> dict[str, Any]:
    fixtures_root, output = Path(fixtures_root).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be new/empty; preserve previous runs unchanged")
    output.mkdir(parents=True, exist_ok=True)
    if split not in {"train", "validation", "test"}:
        raise ValueError("Unsupported split")
    inputs_path = fixtures_root / "inputs.json"
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    selected = [item for item in inputs if item["split"] == split]
    if not selected:
        raise ValueError("No input clips for split")
    allowed = {"clip_id", "path", "sha256", "split", "source", "recipe_id", "start_state"}
    for item in selected:
        if set(item) != allowed or item["source"] != SOURCE:
            raise ValueError("Unexpected input fields/source; possible label leakage")
        if sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("Input video hash mismatch")
    if analyzer is None:
        from .engine import analyze_video
        analyzer = analyze_video
    if recipe is None:
        from .recipe import load_recipe
        recipe = load_recipe("demo_panel_v1")
    snapshot = _source_snapshot(recipe)
    manifest = {
        "status": "RUNNING", "source": SOURCE, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": split, "n_unique_clips": len(selected), "policies": list(POLICIES),
        "inputs_sha256": sha256(inputs_path), "protocol_sha256": sha256(fixtures_root / "protocol.json"),
        "assets": {item["clip_id"]: item["sha256"] for item in selected},
        "code_revision": _revision(Path(__file__).parent), "source_snapshot": snapshot,
        "opencv_version": cv2.__version__, "numpy_version": np.__version__,
        "platform": platform.platform(), "python": platform.python_version(), "processor": platform.processor(),
        "calibration_quad": QUAD, "final_checkpoint": True, "source_mode": "STREAM_REPLAY",
        "threshold_selection": "Engine/recipe settings and fixture protocol fixed before scoring; no test-set tuning.",
        "comparison": "Identical clip SHA, recipe, calibration, start context and policy budget caps; actual extra-frame use is reported, not assumed equal.",
        "label_separation": "annotations.jsonl opened only after all predictions saved; no expected status/error/onset/boundary/frame truth passed to runtime.",
        "real_video_benchmark": {"status": "NOT_RUN", "reason": "No matched authorized real/staged video and reviewed labels supplied."},
    }
    _save(output / "run_manifest.json", manifest)
    predictions = []
    for item in selected:
        for policy in POLICIES:
            result_path = output / "predictions" / f"{item['clip_id']}_{policy}.json"
            def on_frame(record, board, overlay):
                folder = output / "evidence" / f"{item['clip_id']}_{policy}"
                folder.mkdir(parents=True, exist_ok=True)
                name = folder / f"{record['frame_index']:05d}.jpg"
                if not cv2.imwrite(str(name), overlay, [cv2.IMWRITE_JPEG_QUALITY, 88]):
                    raise RuntimeError("Could not save inference overlay")
                return {"benchmark_overlay": str(name), "benchmark_overlay_sha256": sha256(name)}
            begin = time.perf_counter()
            failure = None
            try:
                result = _plain(analyzer(Path(item["path"]), recipe, policy=policy, calibration_quad=QUAD,
                                         start_state=item["start_state"], final_checkpoint=True, on_frame=on_frame))
                status = result.get("decision", {}).get("status")
                if status not in STATUSES[:-1]:
                    raise ValueError("Engine returned no recognized SafetyDecision status")
                if result.get("source_sha256") != item["sha256"]:
                    raise ValueError("Engine provenance SHA differs from exact input asset")
            except Exception as exc:
                failure = f"{type(exc).__name__}: {exc}"
                status, result = "ERROR", {"decision": {"status": "ERROR"}, "failure": failure}
            latency = (time.perf_counter() - begin) * 1000
            _save(result_path, result)
            predictions.append({"clip_id": item["clip_id"], "asset_sha256": item["sha256"], "policy": policy,
                                "predicted_status": status, "processing_latency_ms": latency,
                                "result": result, "result_path": str(result_path), "result_sha256": sha256(result_path), "runtime_failure": failure})
            _save(output / "prediction_index.json", predictions)
    # Only this point opens evaluator labels, after completed inference.
    labels_path = fixtures_root / "annotations.jsonl"
    labels = {r["clip_id"]: r for r in (json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip())}
    for item in selected:
        if labels[item["clip_id"]]["sha256"] != item["sha256"]:
            raise ValueError("Annotation and runtime asset hashes differ")
    rows = evaluate(predictions, labels)
    summary = summarize(rows)
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()})
    results = {
        "status": "COMPLETED_WITH_FAILURES" if any(p["runtime_failure"] for p in predictions) else "COMPLETED",
        "source": SOURCE, "n_unique_clips": len(selected), "prediction_rows": len(rows),
        "real_video_benchmark": manifest["real_video_benchmark"], "summary": summary, "rows": rows,
        "metric_definitions": {
            "status_accuracy": "Exact final PASS/HOLD/REJECT agreement; every clip retained, including ERROR.",
            "supported_error": "Structured matching reason with existing observation/evidence IDs and timestamp. Final-decision-only errors timed at final analyzed frame and separately tagged.",
            "error_detection_unit": "Clip/error type, not individual event intervals. Matching alert must fall after known onset and before correction end when supplied.",
            "false_clear": "Predicted PASS when expected final state HOLD or REJECT, including uncertainty-only clips.",
            "onset_error_ms": "First supported matching alert video time minus generator observable onset; negative alerts do not count as timely true detection.",
            "lead_time_ms": "Synthetic annotated last safe boundary minus alert video time; not physical or human prevention evidence.",
            "processing_latency_ms": "Complete offline video analysis wall time including saving overlay evidence; not camera-to-alert/UI latency.",
            "normal_false_holds_per_video_hour": "Final false HOLD clip count divided by synthetic normal replay duration; not continuous alarms or operator interruption count.",
            "uncertainty": "Wilson95 descriptive clip interval; shared generator grammar precludes real-world statistical generalization.",
            "not_measured": "Temporal IoU/interval F1 (predictions lack intervals), live camera/UI latency, real-world alarm burden, physical prevention and operator acknowledgements.",
        },
    }
    _save(output / "results.json", results)
    _write_gallery(output, predictions, rows)
    _confusion_image(output / "confusion_matrix.png", summary)
    report = ["# Synthetic procedural software evaluation", "", "**SYNTHETIC SOFTWARE TEST. Real procedural video benchmark: NOT RUN.**", "",
              f"{len(selected)} unique generated clips; {len(rows)} repeated-policy rows. Shared board grammar is integration coverage, not industrial generalization.", "",
              "| Policy | Exact final status | False clears | Timely supported error clips | Processing p50/p95 ms | Mean extra frames |",
              "|---|---:|---:|---:|---:|---:|"]
    for policy, s in summary.items():
        m, latency = s["clip_level_error_detection"], s["processing_latency_ms"]
        report.append(f"| {policy} | {s['final_status_correct']}/{s['n_clips']} | {s['false_clear_clips']} | {m['tp']}/{m['positive_clips']} | {latency['p50']} / {latency['p95']} | {s['mean_extra_inspections']} |")
    report.extend(["", "## Paired deltas versus single", ""])
    for policy in ("random", "agent"):
        report.append(f"- {policy}: exact-status delta {summary[policy]['final_status_accuracy'] - summary['single']['final_status_accuracy']:+.4f}; false-clear delta {summary[policy]['false_clear_clips'] - summary['single']['false_clear_clips']:+d}. Budget caps match; actual actions used are shown above.")
    report.extend(["", "All successes, misses, false passes, false holds, early/late warnings and runtime failures remain in results.csv and gallery. No test labels or timing entered model inference. No thresholds were changed after scoring. Fixed-rate synthetic source-frame gaps are not a variable-frame-rate camera test. Real/staged-video results remain NOT RUN.", ""])
    (output / "ablations.md").write_text("\n".join(report), encoding="utf-8")
    manifest.update(status=results["status"], completed_at_utc=datetime.now(timezone.utc).isoformat(),
                    annotations_sha256=sha256(labels_path), results_sha256=sha256(output / "results.json"),
                    csv_sha256=sha256(output / "results.csv"), unchanged_source_snapshot=_source_snapshot(recipe) == snapshot)
    _save(output / "run_manifest.json", manifest)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    args = parser.parse_args()
    result = run(args.fixtures, args.output, split=args.split)
    print(json.dumps({"status": result["status"], "source": SOURCE, "n_unique_clips": result["n_unique_clips"], "prediction_rows": result["prediction_rows"], "output": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
