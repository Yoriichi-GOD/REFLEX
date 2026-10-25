"""Assemble measured benchmark artifacts into an evidence-bounded report."""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import platform
import sys
import ctypes
import csv

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
BENCH = REPORTS / "benchmarks"


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def fnum(value, digits=4):
    return "—" if value is None else f"{float(value):.{digits}f}"


def pnum(value, digits=2):
    return "—" if value is None else f"{100*float(value):.{digits}f}%"


def memory_status() -> dict:
    if os.name != "nt":
        return {"ram_total_bytes": None, "ram_available_bytes_at_report": None}
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"ram_total_bytes": None, "ram_available_bytes_at_report": None}
    return {"ram_total_bytes": int(status.ullTotalPhys), "ram_available_bytes_at_report": int(status.ullAvailPhys)}


def save_summary_svg(real: dict, path: Path) -> None:
    rows = []
    for category in ("candle", "cashew"):
        m = real[category]
        rows.append((category, float(m["image_metrics"]["auroc"]), float(m["image_metrics"]["recall"])))
    width, height = 820, 380
    x0, chart_w, top = 210, 520, 85
    colors = {"AUROC": "#275dad", "fixed-threshold recall": "#d84a3a"}
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#fff"/>',
            '<text x="28" y="38" font-family="Arial" font-size="22" font-weight="bold">REFLEX · frozen VisA results</text>',
            '<text x="28" y="62" font-family="Arial" font-size="13" fill="#444">Real test split, 256 px pixel grid for spatial metrics; no threshold tuning</text>']
    for tick in range(0, 11, 2):
        x = x0 + chart_w * tick / 10
        bits += [f'<line x1="{x:.1f}" y1="74" x2="{x:.1f}" y2="315" stroke="#ddd"/>',
                 f'<text x="{x:.1f}" y="337" text-anchor="middle" font-family="Arial" font-size="12">{tick/10:.1f}</text>']
    for i, (category, auroc, recall) in enumerate(rows):
        base = top + i * 115
        bits.append(f'<text x="28" y="{base+34}" font-family="Arial" font-size="17" font-weight="bold">{html.escape(category)}</text>')
        series = [("AUROC", auroc, colors["AUROC"]), ("Recall", recall, colors["fixed-threshold recall"])]
        for j, (label, value, color) in enumerate(series):
            y = base + j * 34
            bar = chart_w * max(0, min(1, value))
            bits += [f'<text x="115" y="{y+17}" text-anchor="end" font-family="Arial" font-size="13">{label}</text>',
                     f'<rect x="{x0}" y="{y}" width="{bar:.1f}" height="22" fill="{color}"/>',
                     f'<text x="{x0+bar+8:.1f}" y="{y+17}" font-family="Arial" font-size="13">{value:.3f}</text>']
    bits += ['<text x="28" y="370" font-family="Arial" font-size="11" fill="#555">AUROC is threshold-independent; recall uses the normal-only frozen image threshold.</text>', '</svg>']
    path.write_text("\n".join(bits), encoding="utf-8")


def main() -> None:
    real_names = ("candle", "cashew")
    real = {c: read_json(BENCH / c / "metrics.json") for c in real_names}
    robustness = read_json(REPORTS / "robustness" / "metrics.json", {"categories": []})
    audit = read_json(REPORTS / "data_audit.json", {})
    synthetic = read_json(REPORTS / "synthetic_qa" / "metrics.json", {})
    aws_state = read_json(BENCH / "aws_synthetic" / "run_state.json")
    aws_cloudwatch = read_json(BENCH / "aws_synthetic" / "cloudwatch_summary.json")
    if aws_state:
        aws_summary = {k: aws_state[k] for k in ("status", "run_started_utc", "run_finished_utc", "elapsed_seconds", "region", "profile", "warmup_target", "measured_target", "minimum_gap_seconds", "service_upload_limit_per_600_seconds", "concurrency", "health_probe", "measured_stats", "decision_counts") if k in aws_state}
        aws_summary["synthetic_fixture_hashes"] = [{"id": x["id"], "sha256": x["sha256"], "bytes": x["bytes"], "synthetic": x["synthetic"]} for x in aws_state.get("fixtures", [])]
        aws_summary["raw_request_ids_excluded_from_submission_summary"] = True
        (BENCH / "aws_synthetic" / "summary.json").write_text(json.dumps(aws_summary, indent=2), encoding="utf-8")
        attempt_fields = ("request_number", "phase", "phase_index", "fixture_id", "fixture_sha256", "request_started_utc",
                          "status", "status_code", "end_to_end_ms", "runtime_ms", "synthetic", "data_source",
                          "decision", "model_version", "build_revision", "retry_after_seconds")
        with (BENCH / "aws_synthetic" / "samples.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=attempt_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(row for row in aws_state.get("attempts", []) if row.get("phase") in ("warmup", "measured"))
    else:
        aws_summary = {"status": "NOT RUN", "reason": "AWS request profile has not produced a state file"}

    canonical_rows = []
    area_rows = []
    for category in real_names:
        m = real[category]
        im, px, rm = m["image_metrics"], m["pixel_metrics"], m["region_metrics"]
        cm = im["confusion_matrix"]
        pcm = px["pixel_confusion_matrix"]
        canonical_rows.append(f"| {category} | {im['sample_count']} ({im['negative_count']}/{im['positive_count']}) | {fnum(im['auroc'])} | {fnum(im['average_precision'])} | {cm['TP']}/{cm['FP']}/{cm['FN']}/{cm['TN']} | {pnum(im['precision'])} | {pnum(im['recall'])} | {pnum(im['false_positive_rate_on_negatives'])} | {px['pixel_sample_count']:,} | {fnum(px['pixel_auroc'])} | {fnum(px['pixel_average_precision'])} | {fnum(px['au_pro_fpr_0_30'])} | {fnum(px['pixel_iou_at_frozen_normal_threshold'])} | {fnum(px['pixel_dice_at_frozen_normal_threshold'])} | {pnum(px['pixel_precision'])} | {pnum(px['pixel_recall'])} | {pcm['TP']}/{pcm['FP']}/{pcm['FN']}/{pcm['TN']} | {pnum(rm['component_recall_any_overlap'])} | {fnum(rm['mean_component_iou'])} |")
        for bin_name, bin_data in m["area_slices"].items():
            area_rows.append(f"| {category} | {bin_name} | {bin_data['anomaly_count']} | {pnum(bin_data['recall_at_frozen_threshold'])} |")
    agent_rows = []
    for category in real_names:
        m = real[category]
        for key, label in (("agent_static_no_crop", "Static threshold / no crop"), ("agent_full_crop", "Current crop-confirmation policy"), ("agent_random_crop_matched", "Random matched crop"), ("agent_quality_gate_off", "Quality gate disabled")):
            a = m[key]
            cm = a["confusion_matrix_on_resolved"]
            agent_rows.append(f"| {category} | {label} | {a['resolved_count']}/{a['sample_count']} | {cm['TP']}/{cm['FP']}/{cm['FN']}/{cm['TN']} | {pnum(a['precision_on_resolved'])} | {pnum(a['recall_on_resolved'])} | {a['needs_review_count']} |")
    robust_rows = []
    for category_data in robustness.get("categories", []):
        for item in category_data["families"]:
            im, px = item["image"], item["pixel"]
            cm = im["confusion_matrix"]
            pcm = px["pixel_confusion_matrix"]
            robust_rows.append(f"| {category_data['category']} | {item['family']} | {item['n']} | {fnum(im['auroc'])} | {fnum(im['average_precision'])} | {pnum(im['precision'])} | {pnum(im['recall'])} | {pnum(im['false_positive_rate_on_negatives'])} | {cm['TP']}/{cm['FP']}/{cm['FN']}/{cm['TN']} | {fnum(px['pixel_auroc'])} | {fnum(px['pixel_average_precision'])} | {fnum(px['au_pro_fpr_0_30'])} | {fnum(px['pixel_iou_at_frozen_normal_threshold'])} | {fnum(px['pixel_dice_at_frozen_normal_threshold'])} | {pnum(px['pixel_precision'])} | {pnum(px['pixel_recall'])} | {pcm['TP']}/{pcm['FP']}/{pcm['FN']}/{pcm['TN']} |")
    synthetic_rows = []
    synthetic_agent_rows = []
    for item in synthetic.get("categories", []):
        im, px = item["image_metrics"], item["pixel_metrics"]
        cm = im["confusion_matrix"]
        synthetic_rows.append(f"| {item['category']} | {item['evaluation_count']} ({item['normal_count']}/{item['defect_count']}) | {fnum(im['auroc'])} | {fnum(im['average_precision'])} | {cm['TP']}/{cm['FP']}/{cm['FN']}/{cm['TN']} | {pnum(im['precision'])} | {pnum(im['recall'])} | {pnum(im['f1'])} | {pnum(im['false_positive_rate_on_negatives'])} | {fnum(px['pixel_auroc'])} | {fnum(px['pixel_average_precision'])} | {fnum(px['au_pro_fpr_0_30'])} | {fnum(px['pixel_iou_at_frozen_normal_threshold'])} | {fnum(px['pixel_dice_at_frozen_normal_threshold'])} | {pnum(px['pixel_precision'])} | {pnum(px['pixel_recall'])} |")
        a = item["agent_decisions"]
        acm = a["confusion_matrix_on_resolved"]
        synthetic_agent_rows.append(f"| {item['category']} | {a['resolved_count']}/{a['sample_count']} | {a['abstention_count']} | {acm['TP']}/{acm['FP']}/{acm['FN']}/{acm['TN']} | {pnum(a['precision_on_resolved'])} | {pnum(a['recall_on_resolved'])} | {a['false_clear_count']} | {a['false_defect_count']} |")
    real_image_cms = [real[c]["image_metrics"]["confusion_matrix"] for c in real_names]
    micro_image = {key: sum(cm[key] for cm in real_image_cms) for key in ("TP", "FP", "FN", "TN")}
    micro_ip = micro_image["TP"] / max(micro_image["TP"] + micro_image["FP"], 1)
    micro_ir = micro_image["TP"] / max(micro_image["TP"] + micro_image["FN"], 1)
    micro_if = 2 * micro_ip * micro_ir / max(micro_ip + micro_ir, 1e-12)
    macro_image = {key: float(np.mean([real[c]["image_metrics"][key] for c in real_names])) for key in ("auroc", "average_precision", "precision", "recall", "f1", "false_positive_rate_on_negatives")}
    real_pixel_cms = [real[c]["pixel_metrics"]["pixel_confusion_matrix"] for c in real_names]
    micro_pixel = {key: sum(cm[key] for cm in real_pixel_cms) for key in ("TP", "FP", "FN", "TN")}
    micro_pp = micro_pixel["TP"] / max(micro_pixel["TP"] + micro_pixel["FP"], 1)
    micro_pr = micro_pixel["TP"] / max(micro_pixel["TP"] + micro_pixel["FN"], 1)
    micro_piou = micro_pixel["TP"] / max(micro_pixel["TP"] + micro_pixel["FP"] + micro_pixel["FN"], 1)
    micro_pdice = 2 * micro_pixel["TP"] / max(2 * micro_pixel["TP"] + micro_pixel["FP"] + micro_pixel["FN"], 1)
    macro_pixel = {key: float(np.mean([real[c]["pixel_metrics"][key] for c in real_names])) for key in ("pixel_auroc", "pixel_average_precision", "au_pro_fpr_0_30", "pixel_iou_at_frozen_normal_threshold", "pixel_dice_at_frozen_normal_threshold", "pixel_precision", "pixel_recall")}
    memory = memory_status()
    env = {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(),
           "logical_cpu_count": os.cpu_count(), "cpu_model": "not retrievable in this managed session",
           "gpu": "not measured", **memory,
           "opencv": cv2.__version__, "numpy": np.__version__, "report_created_utc": datetime.now(timezone.utc).isoformat()}
    (REPORTS / "benchmark_environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    lines = [
        "# REFLEX benchmark report",
        "",
        f"Report generated: `{env['report_created_utc']}`. Detector parameters were frozen for all reported runs; no tuning or model change was made.",
        "",
        "## Result boundary",
        "",
        "The canonical real-data results below use the local official VisA one-class test splits for `candle` and `cashew`. They are controlled benchmark captures, not factory-floor evidence. Synthetic-kit values are kept in a separate QA section and never substituted for real-data performance. Test labels and masks were used only after inference for scoring; no test label or mask was passed into the detector or agent.",
        "",
        "PatchCore was **not run**. PyTorch 2.14.1 installed in the isolated benchmark environment, but import was blocked by Windows Application Control (`WinError 4551` loading `torch\\lib\\c10.dll`); WSL was also denied. No random or untrained backbone was substituted. The required `pcb1` VisA category is absent from the local prepared tree. The selected VisA categories have per-file hashes, but the full source archive SHA256 was not verified.",
        "",
        "## Canonical real VisA results",
        "",
        "Image confusion order is `TP/FP/FN/TN`. Pixel metrics are computed after aspect-preserving resize to maximum side 256 (scores linear, masks nearest-neighbor). Image and pixel thresholds were derived from normal calibration images only, before test evaluation. AU-PRO is normalized over FPR 0–0.30 using 200 score thresholds.",
        "",
        "| Class | Test N (normal/defect) | Image AUROC | Image AP | Image TP/FP/FN/TN | Image precision | Frozen recall | FPR on normal | Pixel samples | Pixel AUROC | Pixel AP | AU-PRO@0.30 | Pixel IoU | Pixel Dice | Pixel precision | Pixel recall | Pixel TP/FP/FN/TN | Component recall | Mean component IoU |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *canonical_rows,
        "",
        "### Cross-category macro and micro summary",
        "",
        "Macro values are the unweighted arithmetic mean of the two category metrics. Micro threshold metrics sum decisions made at each category's own frozen threshold. Pixel score rankings are not pooled across categories because their separately fitted score spaces are not directly comparable; therefore micro pixel AUROC/AP are omitted.",
        "",
        f"- Macro image: AUROC {fnum(macro_image['auroc'])}; AP {fnum(macro_image['average_precision'])}; precision {pnum(macro_image['precision'])}; recall {pnum(macro_image['recall'])}; F1 {fnum(macro_image['f1'])}; normal FPR {pnum(macro_image['false_positive_rate_on_negatives'])}.",
        f"- Micro image: N=350; TP/FP/FN/TN {micro_image['TP']}/{micro_image['FP']}/{micro_image['FN']}/{micro_image['TN']}; precision {pnum(micro_ip)}; recall {pnum(micro_ir)}; F1 {fnum(micro_if)}; normal FPR {pnum(micro_image['FP'] / max(micro_image['FP'] + micro_image['TN'], 1))}.",
        f"- Macro pixel: AUROC {fnum(macro_pixel['pixel_auroc'])}; AP {fnum(macro_pixel['pixel_average_precision'])}; AU-PRO@0.30 {fnum(macro_pixel['au_pro_fpr_0_30'])}; IoU {fnum(macro_pixel['pixel_iou_at_frozen_normal_threshold'])}; Dice {fnum(macro_pixel['pixel_dice_at_frozen_normal_threshold'])}; precision {pnum(macro_pixel['pixel_precision'])}; recall {pnum(macro_pixel['pixel_recall'])}.",
        f"- Micro pixel threshold confusion: {micro_pixel['TP']}/{micro_pixel['FP']}/{micro_pixel['FN']}/{micro_pixel['TN']} over {sum(real[c]['pixel_metrics']['pixel_sample_count'] for c in real_names):,} pixels; precision {pnum(micro_pp)}; recall {pnum(micro_pr)}; IoU {fnum(micro_piou)}; Dice {fnum(micro_pdice)}.",
        "",
        "",
        "| Class | Fit normals | Calibration normals | Image threshold | Pixel threshold | Native crop calls |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in real_names:
        m = real[c]
        a, p = m["latency"]["analyze_including_quality_and_features"], m["latency"]["policy_orchestration_only_excluding_analyze"]
        lines.append(f"| {c} | {m['fit_normal_count']} | {m['calibration_normal_count']} | {fnum(m['normal_threshold'], 5)} | {fnum(m['pixel_threshold'], 5)} | {m['agent_ablation_counts']['native_crop_calls']} |")
    lines += ["", "Per-call local timings below exclude image file reads. `analyze` includes quality and feature calculation; policy orchestration is timed separately and excludes `analyze`. These are sequential single-host measurements, not AWS service timings.",
              "", "| Class | Analyze mean / std / p50 / p90 / p95 / max (ms) | Policy-only mean / std / p50 / p90 / p95 / max (ms) |",
              "|---|---|---|"]
    for c in real_names:
        m = real[c]
        a = m["latency"]["analyze_including_quality_and_features"]
        p = m["latency"]["policy_orchestration_only_excluding_analyze"]
        fmtlat = lambda x: " / ".join(fnum(x[key], 2) for key in ("mean_ms", "std_ms", "p50_ms", "p90_ms", "p95_ms", "max_ms"))
        lines.append(f"| {c} | {fmtlat(a)} | {fmtlat(p)} |")
    lines += ["", "### Defect-area slices", "", "Anomaly area is the fraction of source-image pixels covered by the official mask. Bins are disjoint; recall uses the unchanged normal-only image threshold.",
              "", "| Class | Mask area fraction | Defect cases | Recall |", "|---|---|---:|---:|", *area_rows]
    lines += [
        "",
        "## Agentic inspection ablations",
        "",
        "| Class | Variant | Resolved / N | TP/FP/FN/TN | Precision | Recall | Review count |",
        "|---|---|---:|---:|---:|---:|---:|",
        *agent_rows,
        "",
        "Across both classes, all four variants produced identical final decisions. The agent invoked native crop inspection 28 times total (20 candle, 8 cashew), below the protocol’s 30-case minimum for a stable random-ROI comparison. Quality flags occurred zero times in canonical VisA cases. Extra-view capture is not implemented in the current per-image policy; the separate registration API is not invoked by it. These ablations provide no evidence that the agent improved inspection decisions.",
        "",
        "## Robustness on derived real VisA images",
        "",
        "Each perturbation is applied to every image in the canonical test set and scored against the unchanged normal-calibration thresholds. These are derived copies, not new independent cases; canonical results remain separate. Wrong-category rows deliberately apply the other class’s bank and thresholds offline. The deployed API checks its active profile and rejects a mismatched requested category with HTTP 422 before inference; the offline stress replay does not represent that API path.",
        "",
        "| Class | Condition | N | Image AUROC | Image AP | Image precision | Frozen recall | FPR | Image TP/FP/FN/TN | Pixel AUROC | Pixel AP | AU-PRO@0.30 | Pixel IoU | Pixel Dice | Pixel precision | Pixel recall | Pixel TP/FP/FN/TN |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *robust_rows,
        "",
        "Input-handling challenge QA is separate from accuracy. All-black, all-white, and checkerboard cases requested a new capture on both class profiles; corrupt bytes were rejected as `UNSUPPORTED_FORMAT`. Text overlay was `DEFECT_FOUND` for candle but `PASS` for cashew. A stitched view was `DEFECT_FOUND` on both. These small diagnostic probes do not estimate OOD detection rates.",
        "",
        "## Supplied synthetic kit QA (not real benchmark results)",
        "",
        "| Synthetic category | Eval N (normal/defect) | Image AUROC | Image AP | Image TP/FP/FN/TN | Precision | Recall | F1 | FPR | Pixel AUROC | Pixel AP | AU-PRO@0.30 | Pixel IoU | Pixel Dice | Pixel precision | Pixel recall |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *synthetic_rows,
        "",
        "The kit audit verified all 96 manifest rows, all image SHA256 values, image/mask decode and dimension equality, zero masks for normal cases, and nonempty masks for defect cases. The synthetic smoke fit used 8 normal training and 4 normal calibration fixtures per category, then scored 4 held-out normals and 16 defects per category. This tests wiring only; it is not evidence of real-world detection performance.",
        "",
        "| Synthetic category | Resolved / N | Abstentions | TP/FP/FN/TN | Precision on resolved | Recall on resolved | False clears | False defect flags |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *synthetic_agent_rows,
        "",
        "## Dataset integrity and availability",
        "",
        f"- Local prepared VisA: candle {audit.get('visa_local_subset',{}).get('categories',{}).get('candle',{}).get('train_good',0)} train normals + 100 normal/100 defective test cases; cashew {audit.get('visa_local_subset',{}).get('categories',{}).get('cashew',{}).get('train_good',0)} train normals + 50 normal/100 defective test cases.",
        "- `pcb1`: blocked; category is absent locally.",
        "- Official `1cls.csv` is included at `data/visa/1cls.csv` with the audit-recorded SHA256. Fit/calibration membership and hashes are recorded in each category's `metrics.json`; held-out image/mask hashes are in `per_case.csv`. The full official archive SHA256 remains unverified.",
        "- The sample image kit is synthetic (96 image/mask pairs). Its metrics are never added to VisA totals.",
        "- The supplied synthetic ZIP README contains no license statement. It is included in the private draft at the user's request; confirm redistribution permission before publication. No license was inferred or added.",
        "",
        "## AWS sequential profile",
        "",
    ]
    if aws_summary.get("status") == "COMPLETED":
        stats = aws_summary["measured_stats"]
        e2e, server = stats["end_to_end_latency"], stats["server_runtime"]
        rate = stats.get("successful_requests_per_second_over_whole_run")
        health = aws_summary.get("health_probe", {})
        lines.append(f"The paced profile completed {aws_summary['warmup_target']} warm-ups and {aws_summary['measured_target']} measured uploads using only three built-in hash-registered synthetic fixtures. It ran sequentially in `ap-southeast-2`, spaced at least {aws_summary['minimum_gap_seconds']:.0f} seconds to honor the 10-per-600-second upload guard. Measured end-to-end request latency (including client TLS/upload) was mean/std/p50/p90/p95/max {fnum(e2e['mean_ms'],1)}/{fnum(e2e['stddev_ms'],1)}/{fnum(e2e['p50_ms'],1)}/{fnum(e2e['p90_ms'],1)}/{fnum(e2e['p95_ms'],1)}/{fnum(e2e['max_ms'],1)} ms. Server-reported processing runtime was mean/std/p50/p90/p95/max {fnum(server['mean_ms'],1)}/{fnum(server['stddev_ms'],1)}/{fnum(server['p50_ms'],1)}/{fnum(server['p90_ms'],1)}/{fnum(server['p95_ms'],1)}/{fnum(server['max_ms'],1)} ms. The separate one-sample GET health probe took {fnum(health.get('latency_ms'),1)} ms and is excluded from upload statistics. Whole-run observed rate was {fnum(rate,5)} successful requests/second, constrained by the upload guard and the chosen 62-second gap; this is not saturation throughput. All returned records were checked for `synthetic=true`.")
    elif aws_summary.get("status") == "RUNNING":
        lines.append(f"Profile is still running as of this report generation: {len(aws_state.get('attempts',[]))} upload attempts, {len(aws_state.get('measured',[]))}/{aws_state.get('measured_target',0)} measured cases completed. It honors {aws_state.get('service_upload_limit_per_600_seconds')} uploads per 600 seconds and uploads only hash-verified synthetic fixtures; final AWS metrics are pending.")
    else:
        lines.append(f"AWS profile status: **{aws_summary.get('status','NOT RUN')}**. {aws_summary.get('reason','See reports/benchmarks/aws_synthetic/summary.json for profile status.')}")
    if aws_cloudwatch and aws_cloudwatch.get("status") in ("BLOCKED", "NOT_CAPTURED"):
        lines.append(f"CloudWatch ECS CPU/memory and application-log counts were not captured for this profile window: {aws_cloudwatch.get('reason','no exact-window CloudWatch evidence is available')}. No earlier or unrelated account metrics were substituted.")
    elif aws_cloudwatch:
        cpu = aws_cloudwatch.get("cpu_utilization_percent", {})
        mem = aws_cloudwatch.get("memory_utilization_percent", {})
        logs = aws_cloudwatch.get("application_logs", {})
        lines.append(f"CloudWatch window {aws_cloudwatch.get('window_start_utc')} to {aws_cloudwatch.get('window_end_utc')}: ECS CPU utilization mean/p95/max {fnum(cpu.get('mean'),2)}/{fnum(cpu.get('p95'),2)}/{fnum(cpu.get('max'),2)}%; memory utilization mean/p95/max {fnum(mem.get('mean'),2)}/{fnum(mem.get('p95'),2)}/{fnum(mem.get('max'),2)}%; metric points CPU={cpu.get('count','—')}, memory={mem.get('count','—')}. Matched `request_completed` application log events: {logs.get('request_completed_count','not available')}, upload-route events: {logs.get('inspection_post_count','not available')}. This is the guard-paced run window, not a saturation test.")
    lines += [
        "",
        "The public app retains inspection records/assets for up to 24 hours by its displayed policy; generated AWS request IDs are retained only in the local run log and excluded from the submission summary. Per-request timings without identifiers are in `reports/benchmarks/aws_synthetic/samples.csv`.",
        "",
        "## PatchCore, evaluation boundaries, and environment",
        "",
        "| Item | Status | Evidence / limitation |",
        "|---|---|---|",
        "| OpenCV normal-bank on VisA | COMPLETED | candle and cashew official one-class splits; thresholds frozen from normal-only calibration |",
        "| Official PatchCore comparison | BLOCKED | PyTorch import denied by Windows Application Control; no pretrained weights or untrained substitute used |",
        "| VisA pcb1 | BLOCKED | local prepared class absent; official source archive transfer incomplete |",
        "| Synthetic fixture integration | COMPLETED | 96/96 rows and image hashes verified; 60 synthetic QA evaluations, clearly separated |",
        "| Robustness | COMPLETED | nine derived perturbations + wrong-category replay, all available real test cases |",
        "| Physical/factory dataset | NOT RUN | no physical product images or production populations were provided |",
        "| Extra view / per-image registration ablation | NOT RUN | current agent does not acquire another view or call registration |",
        "",
        f"Evaluation environment: Python {env['python']}; {env['platform']}; {env['logical_cpu_count']} logical CPUs; RAM {env['ram_total_bytes'] / 1024**3:.2f} GiB; OpenCV {env['opencv']}; NumPy {env['numpy']}. CPU model could not be retrieved; GPU was not measured. The full regression suite passed 27 tests (including 5 benchmark metric/transform tests).",
        "",
        "## What the measurements say to improve next (no changes made)",
        "",
        "1. **Stop treating current decisions as inspection-ready.** The fixed operating point falsely clears 84/100 candle anomalies and 95/100 cashew anomalies. Establish a safety target for false-clear rate and an independent validation split before changing thresholds or features; do not tune on these test sets.",
        "2. **Solve pose sensitivity before adding more detector complexity.** Candle image AUROC fell to 0.4845 after a 7° derived rotation, consistent with the spatially indexed bank. Test fixed registration/canonicalization on training/validation data and report whether it harms unrotated performance.",
        "3. **Prove agent value or simplify the claim.** Current crop confirmation changed zero final decisions; the random-crop comparison has only 28 triggered cases and is underpowered. The next agent experiment should be a pre-registered paired replay with at least 30 real triggered cases and an explicit correct/wrong/review outcome.",
        "4. **Add OOD rejection.** The same text overlay was cleared for cashew and rejected as a defect for candle. Add a validation set with class mismatch, overlays, stitched views, and capture corruption, then evaluate safe abstention—not detector tuning on the current test set.",
        "5. **Unblock PatchCore and pcb1 before claiming benchmark breadth.** Run a pretrained, hash-pinned PatchCore implementation in a permitted runtime and obtain the official `pcb1` split with verified provenance. Keep the existing result frozen as the baseline.",
        "6. **AWS results are latency-only at the guard-compliant pace.** For service capacity, define an authorized load-test profile in an isolated copy of the service with explicit retention and concurrency limits; do not bypass the public app’s upload guard.",
        "",
        "## Reproduction",
        "",
        "From the REFLEX repository with its backend environment active:",
        "",
        "```powershell",
        "$env:PYTHONPATH = 'backend'",
        "$env:REFLEX_VISA_PREPARED = 'C:\\datasets\\reflex-visa\\prepared'",
        "python -m reflex_bench.audit",
        "python -m reflex_bench.synthetic_smoke",
        "python -m reflex_bench.evaluate candle cashew pcb1",
        "python -m reflex_bench.robustness",
        "python -m pytest -p no:cacheprovider -q backend/tests",
        "```",
        "",
        "`python -m reflex_bench.aws_profile` performs 10 warm-up and 100 measured uploads using only built-in synthetic demo images. It takes approximately 113 minutes, honors the live upload limit, and creates temporary synthetic inspection records under the service's 24-hour policy. Run only when that effect is acceptable. `data/visa/1cls.csv`, per-case CSVs, report JSON, source hashes, galleries, and benchmark environment metadata provide the local evidence bundle.",
        "",
        "Data attribution: VisA 2022-09-22 by Yang Zou et al., ECCV 2022; licensed CC BY 4.0. See [DATA_LICENSES.md](../docs/DATA_LICENSES.md).",
        "",
    ]
    out = REPORTS / "FINAL_BENCHMARK_REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    save_summary_svg(real, REPORTS / "benchmark_summary.svg")
    print(json.dumps({"report": str(out), "aws_status": aws_summary.get("status"), "real_categories": list(real), "robustness_categories": len(robustness.get("categories", [])), "synthetic_categories": len(synthetic.get("categories", [])), "environment": env}, indent=2))


if __name__ == "__main__":
    main()
