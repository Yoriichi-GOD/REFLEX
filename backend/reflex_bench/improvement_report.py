"""Render the measured comparison, paired resampling, and diagnostic gallery."""
from __future__ import annotations
import csv
from datetime import datetime,timezone
import html
import json
from pathlib import Path

import numpy as np
from app.core.patch_memory import digest
from reflex_bench.metrics import binary_auroc

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"reports"/"improvement_20261024"


def load(path):return json.loads(path.read_text(encoding="utf-8"))
def csv_rows(path):
    with path.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def fmt(value):return "—" if value is None else f"{value:.6f}" if isinstance(value,float) else str(value)


def main():
    lines=["# REFLEX measured detector improvement — 24 October 2026", "",
           "The original spatial normal bank is preserved. The replacement compares location-independent pretrained patches through OpenCV 5 DNN. All numbers below were measured locally; the changed model has not been benchmarked on AWS.","",
           "## Scope and evidence", "",
           "350 real VisA official test images: candle 100 normal +100 defective; cashew 50 normal +100 defective. These test images were previously evaluated and informed diagnosis. This is a reused-test development comparison, not fresh blind evidence. No defect/test labels or masks entered fitting, calibration, memory construction, or threshold selection. Masks are read after canonical prediction. Nine deterministic perturbations add 3,150 predictions; they are derived images, not independent real captures.","",
           "Frozen protocol/configuration hashes: [freeze.json](freeze.json). Normal-only fitting, calibration and independent development memberships are recorded per category. Fit counts are 648/324, calibration counts 180/90, and reserved development normals 72/36. Baseline used 720/360 fitting normals; reserving validation reduces the candidate fitting set. The candidate uses the same original calibration membership and a 95th-percentile normal image threshold; thresholds were not tuned on test labels.","",
           "## Image detection at frozen normal thresholds","",
           "| Category / metric | Original | Candidate | Change |","|---|---:|---:|---:|"]
    comparisons={};all_rows=[];metrics_by_category={}
    for category in ("candle","cashew"):
        old=load(ROOT/"reports"/"benchmarks"/category/"metrics.json")
        new=load(OUT/category/"metrics.json");metrics_by_category[category]=new
        a,b=old["image_metrics"],new["image_metrics"]
        for key in ("auroc","average_precision","precision","recall","f1","false_positive_rate_on_negatives"):
            lines.append(f"| {category} {key} | {fmt(a[key])} | {fmt(b[key])} | {fmt(b[key]-a[key])} |")
        for key in ("TP","FP","FN","TN"):
            av,bv=a["confusion_matrix"][key],b["confusion_matrix"][key]
            lines.append(f"| {category} {key} | {av} | {bv} | {bv-av:+d} |")
        baseline_rows={r["case_id"]:r for r in csv_rows(ROOT/"reports"/"benchmarks"/category/"per_case.csv")}
        current=csv_rows(OUT/category/"per_case.csv")
        y=np.array([int(r["label"]) for r in current]);before=np.array([float(baseline_rows[r["case_id"]]["score"]) for r in current]);after=np.array([float(r["score"]) for r in current])
        assert all(r["image_sha256"]==baseline_rows[r["case_id"]]["image_sha256"] and r["label"]==baseline_rows[r["case_id"]]["label"] for r in current)
        rng=np.random.default_rng(20261024);ids=[np.flatnonzero(y==label) for label in (0,1)];deltas=[]
        for _ in range(2000):
            selection=np.concatenate([rng.choice(group,len(group),replace=True) for group in ids])
            deltas.append(binary_auroc(y[selection],after[selection])-binary_auroc(y[selection],before[selection]))
        ci=np.quantile(deltas,[.025,.975]).tolist()
        comparisons[category]={"paired_test_image_sha256_match":True,"auroc_delta":b["auroc"]-a["auroc"],"paired_stratified_bootstrap_delta_95pct":ci,"bootstrap_replicates":2000,"seed":20261024}
        all_rows.extend([dict(r,category=category) for r in current])
    lines += ["","## Pixel localization","","All pixel metrics use the same aspect-preserving maximum-side256 grid as the original evaluator. Thresholds come from normal calibration. High pixel AUROC does not imply precise masks.","",
              "| Category / metric | Original | Candidate | Change |","|---|---:|---:|---:|"]
    for category,new in metrics_by_category.items():
        old=load(ROOT/"reports"/"benchmarks"/category/"metrics.json")
        for key,value in new["pixel_metrics"].items():
            if isinstance(value,(int,float)) and key!="pixel_threshold":
                previous=old["pixel_metrics"][key]
                lines.append(f"| {category} {key} | {fmt(previous)} | {fmt(value)} | {fmt(value-previous)} |")
        for key in ("TP","FP","FN","TN"):
            a,b=old["pixel_metrics"]["pixel_confusion_matrix"][key],new["pixel_metrics"]["pixel_confusion_matrix"][key]
            lines.append(f"| {category} pixel {key} | {a} | {b} | {b-a:+d} |")
    lines += ["","## Paired AUROC uncertainty","","2,000 stratified paired image bootstrap samples per category; percentile95% interval for candidate minus original AUROC. These intervals describe this reused finite test set and do not remove development reuse bias.","",
              "| Category | Delta | 95% interval |","|---|---:|---|"]
    for category,comparison in comparisons.items():
        lo,hi=comparison["paired_stratified_bootstrap_delta_95pct"]
        lines.append(f"| {category} | {fmt(comparison['auroc_delta'])} | [{fmt(lo)}, {fmt(hi)}] |")
    lines += ["","## Robustness with unchanged thresholds","","Each row contains every test image in its category. Perturbation generation is deterministic. Defect downsizing uses evaluator masks to create a diagnostic composite; it is not a new real sample. The detector receives only its resulting image.","",
              "| Category / variant | AUROC | AP | Recall | FPR | F1 | TP/FP/FN/TN | Pixel AUROC | Pixel AP | AU-PRO | IoU | Dice | p95 ms |",
              "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for category,new in metrics_by_category.items():
        for name,data in new["robustness"].items():
            m,p=data["image"],data["pixel"];cm=m["confusion_matrix"]
            values=[m["auroc"],m["average_precision"],m["recall"],m["false_positive_rate_on_negatives"],m["f1"]]
            tail=[p["pixel_auroc"],p["pixel_average_precision"],p["au_pro_fpr_0_30"],p["pixel_iou_at_frozen_normal_threshold"],p["pixel_dice_at_frozen_normal_threshold"],data["latency"]["p95_ms"]]
            lines.append(f"| {category} {name} | "+" | ".join(map(fmt,values))+" | "+"/".join(str(cm[k]) for k in ("TP","FP","FN","TN"))+" | "+" | ".join(map(fmt,tail))+" |")
    lines += ["","## Latency and operational decisions","","Local CPU, OpenCV5.0.0, four OpenCV and four OpenBLAS threads, batch1, no GPU. Canonical times include quality checking, localization and inference; robustness timings measure prediction only. AWS measurements in the baseline bundle describe the old synthetic model and cannot be transferred here.","",
              "| Category | Mean ms | Std ms | p50 ms | p90 ms | p95 ms | Max ms | Coverage | False clears | Review |","|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for category,new in metrics_by_category.items():
        l,d=new["latency"],new["decisions"]
        lines.append(f"| {category} | "+" | ".join(fmt(l[k]) for k in ("mean_ms","std_ms","p50_ms","p90_ms","p95_ms","max_ms"))+f" | {fmt(d['coverage'])} | {d['false_clear_count']} | {d['abstention_count']} |")
    cm={k:sum(m["image_metrics"]["confusion_matrix"][k] for m in metrics_by_category.values()) for k in ("TP","FP","FN","TN")}
    comparisons["combined_confusion_matrix"]=cm
    lines += ["",f"Combined candidate confusion matrix: TP={cm['TP']}, FP={cm['FP']}, FN={cm['FN']}, TN={cm['TN']}. Original: TP21/FP7/FN179/TN143. Raw threshold predictions and abstention-aware application decisions are reported separately in each category metrics file.","",
              "## What changed and what remains weak","",
              "- Removed the fixed-coordinate normal reference for these two real-image profiles. Normal patches can match normal reference patches at other positions. The graph preserves pretrained weights and uses exact Euclidean nearest-neighbor scoring.",
              "- Added independent normal development checks, published artifact hashes, deterministic coreset construction, weight and memory tamper rejection, category-aware traces, and profile-matched UI evaluation results.",
              "- Disabled the invalid crop-to-full-spatial-reference confirmation in the new profile. The new policy uses full-image evidence, quality retakes, and human review for missing localization. A useful independent reinspection action and same-budget random control remain unproved; no agentic accuracy gain is claimed.",
              "- Recall remains inadequate for automatic industrial acceptance: candle misses58/100 defects and cashew30/100. Pixel masks remain broad: cashew pixel precision fell from0.3361 to0.2376 despite improved recall and IoU. Review the low-scoring defective examples before further work.",
              "- Center20% black occlusion still causes100% normal false alarms in both categories. Pose robustness improved, but cashew rotation AUROC is0.8618 compared with0.9476 on canonical images. These remaining robustness failures are retained, not removed from the averages.",
              "- Official WideResNet PatchCore remains blocked by the Windows PyTorch library restriction. This adapted ResNet50 patch-memory method differs in backbone, feature aggregation, projection, coreset and preprocessing; do not label its numbers as official PatchCore.",
              "- Fresh independent evaluation, pcb1, all12 VisA classes, other real datasets, actual multi-view evidence, changed-model AWS latency/resource measurements, and final competition publication remain outstanding. The original two-class acquisition and dataset/archive limitations still apply.","",
              "## Next work, with evidence gates","",
              "1. Reserve a new independent real validation set before another detector iteration. Keep the official test replay frozen. Evaluate pcb1 separately when legitimately available; do not pool categories to hide a weak class.",
              "2. Test higher-resolution or separately calibrated scale-specific local inspection for tiny candle defects. Choose settings using the development set and normal false alarms, then measure recall and latency on independent real labels. Do not lower the image threshold on these exposed test labels.",
              "3. Add explicit occlusion/capture suitability checks using labeled development captures, and measure retake precision/recall. Improve mask specificity using development data; report the lost defect recall if tightening segmentation.",
              "4. Calibrate any second-look evidence at its own scale and compare its chosen ROI with a matched random ROI on at least30 real cases. Record decision changes, extra time and unresolved cases. Run the actual changed DNN path on AWS before updating AWS speed or cost claims.","",
              "## Reproduce and inspect","",
              "See [protocol](../../docs/IMPROVEMENT_PROTOCOL_20261024.md), [local profile instructions](../../docs/PATCH_PROFILE.md), [candle full metrics](candle/metrics.json), [cashew full metrics](cashew/metrics.json), [all comparisons](comparison.json), and [gallery](gallery.html). Per-category CSV files contain all canonical and robustness predictions and measured latency. Membership manifests list hashes for fit, calibration and development normals.","",
              "Canonical image masks were evaluated only after model prediction. All inputs, outputs, thresholds and comparisons are tied to hashes. The previous baseline archive is unchanged: SHA2561503ceb71c4ccd271928b806cc4980ee46110b515edebfbd9078c905a9230b90.","",
              "## Sources and image rights","",
              "Pretrained artifact: [official ONNX ResNet model zoo](https://github.com/onnx/models/tree/main/validated/vision/classification/resnet), Apache2.0. [Official Git LFS hash](https://raw.githubusercontent.com/onnx/models/main/validated/vision/classification/resnet/model/resnet50-v1-12.onnx). Algorithm inspiration: [Amazon Science PatchCore implementation](https://github.com/amazon-science/patchcore-inspection). We do not claim equivalence to its released model.","",
              "Gallery contains resized VisA images with model overlays and mask tints: derived illustrations from [VisA, Amazon Science](https://github.com/amazon-science/spot-diff), [CC BY4.0](https://creativecommons.org/licenses/by/4.0/). Reference: Zou et al., SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation, ECCV2022. Labels and ground truth appear only in evaluation artifacts."]
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (OUT/"comparison.json").write_text(json.dumps(comparisons,indent=2),encoding="utf-8")
    cards=[]
    for category in metrics_by_category:
        records=csv_rows(OUT/category/"per_case.csv")
        for path in sorted((OUT/category/"gallery").glob("*.jpg")):
            r=records[int(path.stem)];outcome=("missed defect" if r["label"]=="1" and r["prediction"]=="0" else "false alarm" if r["label"]=="0" and r["prediction"]=="1" else "correct")
            cards.append(f'<figure data-category="{category}" data-outcome="{outcome}"><figcaption>{category} · {html.escape(r["case_id"])} · {outcome} · score {float(r["score"]):.4f} / threshold {float(r["threshold"]):.4f}</figcaption><img loading="lazy" src="{path.relative_to(OUT).as_posix()}" alt="Input, candidate heatmap, evaluator-only ground truth"></figure>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>REFLEX measured improvement gallery</title><style>body{font:16px system-ui;background:#101820;color:#e9f0f5;margin:30px auto;max-width:1200px;padding:0 18px}a{color:#63dcca}figure{margin:24px 0;background:#1b2a36;padding:12px}img{display:block;max-width:100%;margin-top:10px}select{padding:8px}p{max-width:900px;line-height:1.5}</style><h1>REFLEX real-image evaluation gallery</h1><p>Input / model evidence / evaluator-only ground truth. High and low scores from both real VisA classes, including remaining failures. These examples are selected by score, not a random performance estimate. The official test split was reused during development.</p><p><a href="REPORT.md">Measured report</a> · VisA images: Amazon Science, Zou et al., ECCV2022, CC BY4.0; resized and overlaid here.</p><label>Category <select id="category"><option value="all">All</option><option>candle</option><option>cashew</option></select></label> <label>Outcome <select id="outcome"><option value="all">All</option><option>missed defect</option><option>false alarm</option><option>correct</option></select></label>'''+"".join(cards)+'''<script>function filter(){document.querySelectorAll('figure').forEach(f=>f.hidden=!(['category','outcome'].every(k=>document.getElementById(k).value==='all'||f.dataset[k]===document.getElementById(k).value)))}document.querySelectorAll('select').forEach(s=>s.addEventListener('change',filter))</script></html>'''
    (OUT/"gallery.html").write_text(page,encoding="utf-8")
    print(json.dumps(comparisons,indent=2))


if __name__=="__main__":main()
