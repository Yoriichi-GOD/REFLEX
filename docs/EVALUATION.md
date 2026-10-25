# Evaluation

Latest: the authorized detector improvement and reused VisA test replay are in the [measured improvement report](../reports/improvement_20261024/REPORT.md). Candidate image AUROC is0.9005/0.9476 and recall0.42/0.70 for candle/cashew. Original results below remain historical evidence. Both real models now run on AWS with six verified real-image smoke cases and a side-by-side photograph/heatmap/overlay gallery; see the [release evidence](../reports/real_demo_20261024/RELEASE.md). A full new-model AWS performance benchmark and agentic reinspection benefit remain unmeasured.

For the expanded 2026-10-24 pass (256-side pixel maps, AU-PRO, real-data agent ablations, robustness, full synthetic-kit integrity, and AWS profile status), see the [complete benchmark report](../reports/FINAL_BENCHMARK_REPORT.md). The historical result sections below remain for traceability.

## Complete benchmark pass (2026-10-24)

The updated frozen-model results, all pixel and agent ablation metrics, robustness tables, input challenge QA, data audit, local galleries, environment record, and AWS profile status are collected in the [REFLEX benchmark report](../reports/FINAL_BENCHMARK_REPORT.md). Reproduction code is in `backend/reflex_bench/`, and the official VisA one-class index is included at `data/visa/1cls.csv`.

This pass evaluates the available official `candle` and `cashew` splits (200 and 150 test cases) with thresholds derived from disjoint normal-only calibration subsets. It does not tune the detector. The requested synthetic kit is separately integrity-checked and evaluated as QA only. `pcb1`, PatchCore, physical-product data, and per-image true-view/registration experiments remain blocked or not implemented; see the report's status table.

The new pixel protocol evaluates aspect-preserving score and mask maps at maximum side 256 and reports AU-PRO. The earlier synthetic-only table below retains its 120×90 feature-grid metrics for traceability; do not combine those pixel numbers with the new report's 256-grid results.

## Current measured run

Run `20261023T193302585414Z` on the REFLEX seeded synthetic holdout. This is not a MVTec, physical-camera, factory, or AWS benchmark.

The separately recorded AWS smoke confirms a successful synthetic request against the deployed OpenCV 5 image and its CloudWatch events. It is one end-to-end operational check, not part of the 32-case holdout or a performance benchmark; see [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md).

| Split | Count |
|---|---:|
| Normal training | 40 |
| Normal calibration | 12 |
| Held-out normal | 12 |
| Held-out synthetic defect | 20 |

The train and calibration folders use disjoint seed ranges from the evaluation folders. `fit_demo.py` receives only `train_normal` and `calibration_normal`. The evaluator alone reads defect labels and masks after loading the frozen model and thresholds. No test labels tune the model.

| Image metric | Measured value |
|---|---:|
| Image AUROC | 0.987500 |
| Precision at frozen threshold | 0.947368 |
| Recall at frozen threshold | 0.900000 |
| F1 at frozen threshold | 0.923077 |
| Confusion TP / FP / FN / TN | 18 / 1 / 2 / 11 |
| False-positive rate on held-out normals | 0.083333 |
| Pixel AUROC | 0.998488 |
| Pixel IoU at normal-calibrated pixel threshold | 0.291960 |
| Pixel precision / recall | 0.298053 / 0.934563 |

Pixel metrics use the exact generated masks. The pixel threshold is the 99.5th percentile of normal calibration-map pixels; it is a finite-sample heuristic. The image threshold is the 95th percentile of 12 normal calibration-image scores. Neither value is a probability or a guaranteed production false-positive rate.

Agent branched on 19/32 cases. Mean tool calls: 1.5938; decisions changed versus score-threshold-only: 0; false clear on synthetic defects: 2/20; additional policy time mean: 1.0477 ms. On this fixed set the second pass did not change the final decisions or reduce the observed errors. It did generate a new crop measurement on selected cases.

Sequential local runtime on Windows-11-10.0.26200-SP0 with 32 samples at 480×360: p50 7.075 ms, p95 11.240 ms, max 131.655 ms. Concurrency was 1; memory was not measured.

## Real-image benchmark: VisA one-class split

The official MVTec AD v1 page reported dataset downloads temporarily unavailable when checked on 2026-10-24. As a supplemental benchmark, REFLEX used the official VisA 2022-09-22 one-class split from Amazon Science. The AWS Open Data registry lists VisA under CC BY 4.0. This is a controlled real-image benchmark; it is not factory-floor or production-line validation.

The archive transfer was incomplete. The retrieved portion contains all raw files for `candle` and `cashew` referenced by the official split CSV; `pcb1` was not obtained. No full archive SHA256 is claimed. Current portable per-case files under `reports/benchmarks/{candle,cashew}/` include each image and mask SHA256; the split CSV SHA256 is `a48557e6033318cb90556f706196bc9d247a776a23ea51aecee5a80dd0332995`. Raw data and fitted model banks remain outside the repository. The submission includes small VisA-derived comparison panels under the CC BY 4.0 attribution stated in [`DATA_LICENSES.md`](DATA_LICENSES.md); it does not include raw VisA images.

For each class, sorted official train/good paths were shuffled with seed `20261023`; 20% were reserved for calibration and the remainder for fitting. The fitter read only these two normal subsets. Test labels and masks were used only after the model bank and thresholds were frozen. The model is the existing OpenCV spatial normal-feature baseline; there is no PatchCore or pretrained backbone in these runs.

| VisA class | Fit normal | Calibration normal | Test normal | Test anomaly | Image AUROC | Precision / recall / F1 at frozen threshold | TP / FP / FN / TN | Test-normal FPR |
|---|---:|---:|---:|---:|---:|---|---|---:|
| candle | 720 | 180 | 100 | 100 | 0.7579 | 0.8000 / 0.1600 / 0.2667 | 16 / 4 / 84 / 96 | 0.0400 |
| cashew | 360 | 90 | 50 | 100 | 0.5988 | 0.6250 / 0.0500 / 0.0926 | 5 / 3 / 95 / 47 | 0.0600 |

The full current pixel evaluation uses aspect-preserving score and mask maps with maximum side 256, and reports pixel AUROC/AP, IoU, Dice, AU-PRO, and threshold confusion counts. The detailed current results are in the [complete benchmark report](../reports/FINAL_BENCHMARK_REPORT.md) and each class's portable `metrics.json` and `per_case.csv` files. The older 120×90 pixel results are superseded and are not repeated here.

The frozen baseline falsely cleared 84/100 candle anomalies and 95/100 cashew anomalies; it raised 4 false alarms among 100 candle normals and 3 among 50 cashew normals. These are measured failure counts, not performance claims. The [complete report](../reports/FINAL_BENCHMARK_REPORT.md) contains current pixel and agent ablations, robustness, challenge QA, and timing distributions. Current portable per-case files contain exact image/mask hashes, scores, decisions, and timings. Historical result JSONs remain local for traceability but are excluded from the submission draft because they embed host paths and refer to the earlier coarse pixel grid.

MVTec AD v1 remains unevaluated. No real physical bench photographs or factory captures were available.

## Observed failures

- `normal_008` — false_defect_by_agent (normal); [computed overlay](../results/failures/20261023T193302585414Z/normal_008_false_defect_by_agent.png).
- `discoloration_00` — false_clear_by_agent (discoloration); [computed overlay](../results/failures/20261023T193302585414Z/discoloration_00_false_clear_by_agent.png).
- `discoloration_02` — false_clear_by_agent (discoloration); [computed overlay](../results/failures/20261023T193302585414Z/discoloration_02_false_clear_by_agent.png).

## Reproduce

```powershell
python backend/scripts/make_fixtures.py
python backend/scripts/fit_demo.py
python backend/scripts/evaluate.py
```

Full JSON: `results/eval_20261023T193302585414Z.json`; per-case timings/tools: `results/latency_20261023T193302585414Z.csv`; machine manifest: `results/environment_20261023T193302585414Z.json`.
