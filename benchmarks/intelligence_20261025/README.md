# Intelligence audit — 25 October 2026

Read the [public intelligence report](../../docs/REFLEX_YMCA_PPT_INTELLIGENCE_PUBLIC.md) for all 85 questions and scope boundaries.

`BENCHMARK_LEDGER.csv` projects 7,363 numeric entries from 347 saved CSV rows. Every numeric value was checked against the already-published `benchmarks/anomaly_v2` table and remains unchanged. Source paths are repository-relative. This is evidence indexing, not a new inference run.

`DERIVED.json` contains reproducible arithmetic, including the conditional AWS compute-only estimate and mixed-population policy accounting. `VERIFICATION.json` records the prior fresh software checks and their limits. The original detailed audit, runtime logs, source freeze/model files and raw datasets remain private local evidence.

## Image attribution and scope

The examples are derived from VisA by Amazon Science: Yang Zou, Jongheon Jeong, Latha Pemula, Dongqing Zhang and Onkar Dabeer, SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation, ECCV 2022. Source: https://github.com/amazon-science/spot-diff . License: https://creativecommons.org/licenses/by/4.0/ . Retain attribution when redistributing.

Panels juxtapose a real photograph, model heatmap, model overlay and evaluator ground truth. Ground truth is evaluator-only after prediction. Detail PNGs are actual crops of that same photograph, not a second camera view. The examples are candle replay bad/068.JPG, bad/021.JPG, bad/029.JPG and capsules final bad/093.JPG. These were selected for explanation and are not a random accuracy estimate. The capsules example is an actual false clear; bad/029.JPG remains unresolved review.

Figures are unchanged exports from frozen measured results. Reused replay, new-category final, image ranking, threshold decisions, policy controls and timing measurements must stay separately labeled. Historical custom AU-PRO is invalid; use the corrected tables. The v2 release is held. Safety Station has no real physical assembly benchmark or AWS video deployment.
