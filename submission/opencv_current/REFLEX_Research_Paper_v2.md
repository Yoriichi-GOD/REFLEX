# REFLEX Visual Inspection with Frozen Comparisons and Corrected Localization Metrics



Abstract

REFLEX couples normal-only visual anomaly scoring with an inspectable evidence and review workflow. We evaluate a fixed candidate against the unchanged adapted v1 detector on 860 published VisA images in eight separate category/population groups. The reused candle/cashew replay contains 350 images; custom development and final partitions cover three additional categories. On the replay, automatic false clears fall from 88 to 41, with 4 unresolved cases. Within the frozen primary policy, review-only, chosen-crop and random-crop paths pass the same defective case IDs; the review band accounts for the policy's false-clear reduction. On the additional-category final partitions, confirmed defect detections rise from 92 to 105 of 150, while normal false alerts rise from 9 to 14 of 105 and 11 cases remain unresolved. Equal-category final macro AUROC falls from 0.85204 to 0.84098. Dedicated AWS handler p95 and peak resident memory increase by 17.35% and 43.90%. An additive AU-PRO correction addresses an analytic failure in the historical metric. The evidence supports keeping the candidate local; it does not establish a new algorithm, official benchmark equivalence or factory readiness.

Index terms   visual anomaly detection   patch memory   calibration   review burden   reproducibility

## Introduction

An anomaly score is only one part of an inspection decision. The operator also needs the inspected image, the supporting region, the threshold, and a record of any second inspection. Ranking quality can improve while automatic false clears, false alerts or review workload remain unsuitable. We therefore evaluate image ranking, threshold decisions, localization and runtime as separate outcomes.

REFLEX uses existing pretrained features and normal patch memories within a deployed evidence viewer. This study evaluates engineering choices and their costs; it does not introduce a new anomaly-detection algorithm. PatchCore motivates nominal patch memories [1], ResNet supplies a pretrained representation [3], and VisA provides public photographs and annotations [2, 4]. The OpenCV adaptation and a separately configured upstream reference are distinct implementations.

The fixed primary is dense128_region. All fixed coverage, projection, scoring, pose and seed variants remain in the supplement, including variants that outperform it on individual groups. No best test arm or seed is selected retrospectively. The release assessment is HOLD_CANDIDATE_LOCAL because the evidence includes category regressions and operational costs.

## Data and evaluation boundaries

Candle and cashew were already used to diagnose the earlier system and remain development replay. Capsules, chewinggum and pcb1 are newly evaluated categories within the same published dataset. Each has separate custom diagnostic-development and final partitions. The final partitions were sealed until the recorded source/model/manifest freeze, and neither published-test half selects a threshold, model setting, seed or hardware choice. These are not new factory captures; physical item, lot and capture identifiers are unavailable.

| Category | Fit normals | Calibration | Normal development | Replay or dev and final |
| --- | --- | --- | --- | --- |
| candle | 648 | 180 | 72 | 200 replay |
| cashew | 324 | 90 | 36 | 150 replay |
| capsules | 391 | 108 | 43 | 80 each partition |
| chewinggum | 326 | 91 | 36 | 75 each partition |
| pcb1 | 651 | 181 | 72 | 100 each partition |

Hash-disjoint fitting, calibration and reserved normal-development membership is recorded. Additional-category acquisition audited all decoded images and masks, checked byte/pixel identities and conservative near-duplicate groups, and retained source provenance. This does not prove capture independence. The complete archive has a locally computed SHA256 and stable HTTP source evidence; an independently published upstream SHA256 was unavailable. Dataset attribution and the CC BY4.0 license accompany the export [4].

The independent image oracle reproduced 88 method/group rows and 9,460 saved predictions. Their unique image denominator remains 860; repeated methods, seeds, crops, stress transforms and service uploads do not increase it. Replay, diagnostic development and final results remain separate throughout.

## Fixed detector and review methods

The OpenCV DNN path uses the verified ImageNet ResNet50 graph with intermediate stage features. The dense baseline samples 96 spatially balanced valid patches per normal image and retains a 4096-patch coreset. The base projection is 128-dimensional; a 512-dimensional arm preserves other declared settings. Alternative image scores use the maximum patch distance, the mean of the four largest valid distances, or the largest local 3 by 3 mean. The last is the predeclared primary. A pose arm adds a deterministic seven-degree rotation of normal fitting images. Derived views are not additional captured parts.

The base memory seed and two fixed repeat seeds are retained for both projection dimensions. The earlier adapted v1 memory and the legacy OpenCV spatial median/MAD detector provide separate baselines with matched normal membership. The classical detector uses its original 120 by 90 internal grid while deep models use a 256 input, so it is a practical comparison rather than a matched-resolution backbone ablation.

The automatic defect boundary is the normal-calibration p95 with the higher quantile convention. A lower PASS boundary is selected from fixed normal-calibration quantiles under a ten-percent reserved-normal review budget in canonical and rotated views. The independent detail memory uses four overlapping corner tiles, each 62.5 percent of source width and height, with a separately fitted and calibrated reference. A suitable case in the review band can receive at most one chosen detail call. Inconclusive evidence remains NEEDS_REVIEW and cannot become an automatic PASS.

Chosen and seeded-random one-tile controls use equal source pixel and logical call budgets. Their batch evaluator also computes all four tiles and reuses those outputs for counterfactual policies; these are not independently timed end-to-end executions. Full-plus-tile fusion has its fixed rule and higher budget recorded, without assuming the union retains the component false-alert budget. Capture suitability is advisory, and the present path does not perform registration or acquire a second physical camera view.

## Metrics and correction

Image AUROC uses half credit for score ties, AP is stepwise average precision, and threshold predictions use score greater than the frozen boundary. Automatic false clears are defective images returned PASS; reviews remain unresolved. Raw detector recall and resolved-decision recall have different denominators and are never substituted for each other. Equal-category macro AUROC is an arithmetic mean of category AUROCs within a population, not a pooled ROC or an independent-trials estimate.

The historical AU-PRO collapsed distinct score transitions with equal false-positive rate to their maximum region recall. This deletes vertical endpoints and can create area before a region is recovered. On the analytic reverse-ranking map it returns 0.15 instead of zero. Historical AU-PRO values and figures are invalid for comparison; the original files are preserved. Other metrics are evaluated separately rather than invalidated by association.

The additive correction keeps every unique float32 score event, merges equal-score ties, preserves vertical segments, weights eight-connected annotated regions equally, and uses all normal pixels including normal images. Trapezoidal area is linearly clipped at FPR 0.30 and divided by 0.30. A constant tied map gives 0.15 under this explicit convention; absent positive regions or negative pixels is undefined. The original non-PRO metric definitions are preserved. Independent literal threshold enumeration and pyaupro reference curves agree on the retained synthetic fixtures [6]. This does not establish byte parity with the publisher metric package: its linked download returned HTTP 404. Official VisA PR-AUC is trapezoidal and differs from stepwise AP [7].

## Image results

| Category population | N | AUROC v1 to primary | Detected v1 to primary | False clears v1 to primary | False alerts v1 to primary | Primary reviews |
| --- | --- | --- | --- | --- | --- | --- |
| candle replay | 200 | 0.9005 to 0.9566 | 42 to 78 / 100 | 58 to 18 | 3 to 6 / 100 | 4 |
| cashew replay | 150 | 0.9476 to 0.9600 | 70 to 77 / 100 | 30 to 23 | 2 to 0 / 50 | 0 |
| capsules development | 80 | 0.7027 to 0.6680 | 16 to 14 / 50 | 34 to 36 | 1 to 2 / 30 | 0 |
| capsules final | 80 | 0.7233 to 0.6713 | 16 to 16 / 50 | 34 to 34 | 0 to 1 / 30 | 0 |
| chewinggum development | 75 | 0.9680 to 0.9912 | 48 to 49 / 50 | 2 to 1 | 0 to 1 / 25 | 3 |
| chewinggum final | 75 | 0.9840 to 0.9736 | 47 to 48 / 50 | 3 to 2 | 3 to 4 / 25 | 1 |
| pcb1 development | 100 | 0.8932 to 0.9112 | 30 to 38 / 50 | 20 to 7 | 3 to 6 / 50 | 7 |
| pcb1 final | 100 | 0.8488 to 0.8780 | 29 to 41 / 50 | 21 to 6 | 6 to 9 / 50 | 10 |

![Image AUROC](image_auroc.png)
Image AUROC on each fixed population. Gray is unchanged v1 and blue is the predeclared primary. Axes begin at 0.5; no uncertainty intervals or pooled performance are implied.

The reused replay reduces automatic false clears from 88 to 41 among 200 defective images, but leaves 4 cases unresolved. The additional-category final groups detect 105 rather than 92 defects, while false alerts rise from 9 to 14 among 105 normals. Their macro AUROC falls from 0.85204 to 0.84098. These outcomes describe a trade-off, not uniform improvement.

Capsules is a specific failure case: final primary AUROC is 0.6713, only 16 of 50 defects are confirmed, and 34 are automatically cleared. Its 0 reviews do not explain that weakness away. Better ranking on the older replay therefore does not justify category-wide release promotion.

## Localization and selective inspection

| Category population | Pixel AUROC | Pixel AP | IoU | Dice | Corrected AU PRO |
| --- | --- | --- | --- | --- | --- |
| candle replay | 0.9818 | 0.1752 | 0.0769 | 0.1429 | 0.9311 |
| cashew replay | 0.9867 | 0.5487 | 0.2697 | 0.4249 | 0.9130 |
| capsules development | 0.9497 | 0.3199 | 0.2038 | 0.3386 | 0.5815 |
| capsules final | 0.9630 | 0.4991 | 0.3362 | 0.5032 | 0.5058 |
| chewinggum development | 0.9803 | 0.5173 | 0.1338 | 0.2360 | 0.7794 |
| chewinggum final | 0.9883 | 0.5548 | 0.1048 | 0.1897 | 0.8430 |
| pcb1 development | 0.9914 | 0.8386 | 0.2037 | 0.3385 | 0.7913 |
| pcb1 final | 0.9918 | 0.8227 | 0.1871 | 0.3153 | 0.8362 |

These candidate localization values use the maximum-side 256 full-source evaluation grid. Native-coordinate threshold counts are retained separately; native ranking values are not inferred from a resized grid. High pixel AUROC does not certify a usable boundary, so precision, recall, IoU, Dice and mask evidence accompany the ranking scores. Map-replay verification has a separate completion receipt; a successful image oracle alone is insufficient to validate localization.

| Category population | Actual active triggers | Trace complete | Thirty trigger criterion |
| --- | --- | --- | --- |
| candle replay | 16 | 16 | not met |
| cashew replay | 0 | 0 | not met |
| capsules development | 0 | 0 | not met |
| capsules final | 0 | 0 | not met |
| chewinggum development | 3 | 3 | not met |
| chewinggum final | 1 | 1 | not met |
| pcb1 development | 12 | 12 | not met |
| pcb1 final | 14 | 14 | not met |

No individual group reaches the declared thirty-case active-trigger target, and some groups have zero triggers. Forced chosen/random controls run on every source case and quantify a different question; they do not supply missing active-trigger evidence. Review rate, coverage, false alerts and false clears remain visible. A favorable forced-crop result cannot be transferred to the deployed selective policy or to an unobserved second camera capture.

## What detail inspection contributes

A post-evaluation descriptive audit of unchanged outcomes finds identical false-clear case-ID sets for review-only, chosen-crop and random-crop paths in every group. The review band removes those automatic passes; crop choice does not further reduce them. Across 46 executed active cases (29 defective and 17 normal), chosen detail resolves 17 additional true alerts and 4 false alerts relative to review without ROI. Random detail resolves 12 true alerts and 2 false alerts. Review-only leaves 46 unresolved, chosen 25, and random 32; all three retain 127 automatic false clears in the execution audit. These cross-population totals audit controller behavior, not pooled generalization or a superiority test.

| Category population | Review only false clears | Chosen and random false clears | Chosen TP FP reviews | Random TP FP reviews |
| --- | --- | --- | --- | --- |
| candle replay | 18 | 18 / 18 | 78 / 6 / 4 | 74 / 4 / 10 |
| capsules development | 36 | 36 / 36 | 14 / 2 / 0 | 14 / 2 / 0 |
| capsules final | 34 | 34 / 34 | 16 / 1 / 0 | 16 / 1 / 0 |
| cashew replay | 23 | 23 / 23 | 77 / 0 / 0 | 77 / 0 / 0 |
| chewinggum development | 1 | 1 / 1 | 49 / 1 / 3 | 49 / 1 / 3 |
| chewinggum final | 2 | 2 / 2 | 48 / 4 / 1 | 48 / 4 / 1 |
| pcb1 development | 7 | 7 / 7 | 38 / 6 / 7 | 37 / 6 / 8 |
| pcb1 final | 6 | 6 / 6 | 41 / 9 / 10 | 41 / 9 / 10 |

The audit is descriptive and does not select or tune a new policy. Chosen and random have equal logical crop budgets but reuse the evaluator tile batch. Small active groups and reused images do not establish selection superiority. Raw detector changes between v1 and the primary remain separate from this within-policy contribution accounting.

## Native coordinate localization

| Category population | Native precision | Native recall | Native IoU | Native Dice |
| --- | --- | --- | --- | --- |
| candle replay | 0.0784 | 0.8109 | 0.0769 | 0.1429 |
| cashew replay | 0.2773 | 0.9083 | 0.2697 | 0.4248 |
| pcb1 development | 0.2074 | 0.9273 | 0.2041 | 0.3390 |
| pcb1 final | 0.1903 | 0.9242 | 0.1874 | 0.3156 |
| chewinggum development | 0.1352 | 0.9420 | 0.1341 | 0.2365 |
| chewinggum final | 0.1054 | 0.9694 | 0.1050 | 0.1901 |
| capsules development | 0.2817 | 0.4261 | 0.2042 | 0.3391 |
| capsules final | 0.4637 | 0.5424 | 0.3333 | 0.4999 |

These native-coordinate values are threshold-count metrics on the original source grid. No native AUROC or AP is claimed. Their denominator differs from both the candidate resized ranking grid and the reference center crop.

## Dependent stress results

The fixed stress evaluation contains nine transformations per evaluated category and population. These are dependent copies of the same photographs. The table reports descriptive extrema across all nine families, without selecting a new method; the extrema in different columns can come from different transformations. Every family and its denominators remain in the accompanying ROBUSTNESS.csv.

| Category population | Lowest raw AUROC | Highest raw normal FPR | Lowest decision coverage |
| --- | --- | --- | --- |
| candle replay | 0.4485 | 100.0% | 0.0% |
| cashew replay | 0.7838 | 100.0% | 8.7% |
| capsules final | 0.5307 | 100.0% | 98.8% |
| chewinggum final | 0.3304 | 100.0% | 0.0% |
| pcb1 final | 0.4048 | 100.0% | 88.0% |

A low false-clear count under stress can result from routing every image to review. Raw scoring, automatic dispositions and unresolved workload therefore need to be read together. Neither these derived perturbations nor the advisory suitability checks validate capture routing on independent factory images.

## Upstream reference comparison

The separately frozen upstream reference completed every declared population. Its image metrics use the same source image memberships, while its pixel results cover only the region visible after short-edge Resize 256 and CenterCrop 224. The exporter verifies the paired image and label identities before comparison.

| Category population | N | Reference AUROC | Reference AP | Reference raw recall | Reference normal FPR |
| --- | --- | --- | --- | --- | --- |
| cashew replay | 150 | 0.9746 | 0.9871 | 0.8300 | 0.0400 |
| candle replay | 200 | 0.9906 | 0.9908 | 0.9100 | 0.0500 |
| capsules development | 80 | 0.7160 | 0.8239 | 0.3600 | 0.1333 |
| capsules final | 80 | 0.8000 | 0.8956 | 0.5200 | 0.0333 |
| chewinggum development | 75 | 0.9928 | 0.9968 | 0.9400 | 0.0000 |
| chewinggum final | 75 | 0.9840 | 0.9935 | 0.9400 | 0.0400 |
| pcb1 development | 100 | 0.9988 | 0.9988 | 0.9800 | 0.0200 |
| pcb1 final | 100 | 0.9644 | 0.9634 | 0.9600 | 0.1000 |

| Reference crop population | Pixel AUROC | Pixel AP | IoU | Corrected AU PRO | Native defect pixels excluded |
| --- | --- | --- | --- | --- | --- |
| cashew replay | 0.9845 | 0.6157 | 0.2757 | 0.9269 | 4661 / 2530212 |
| candle replay | 0.9920 | 0.2543 | 0.0462 | 0.9612 | 1301 / 405291 |
| capsules development | 0.9816 | 0.5456 | 0.2785 | 0.8439 | 165085 / 411973 |
| capsules final | 0.9958 | 0.7806 | 0.4924 | 0.8757 | 61994 / 404371 |
| chewinggum development | 0.9843 | 0.4501 | 0.1200 | 0.8101 | 3 / 663936 |
| chewinggum final | 0.9879 | 0.4878 | 0.0968 | 0.8383 | 0 / 607475 |
| pcb1 development | 0.9973 | 0.8997 | 0.1348 | 0.9295 | 1747 / 695226 |
| pcb1 final | 0.9964 | 0.8895 | 0.1461 | 0.9219 | 71 / 703688 |

Reference crop-only pixel metrics, per-image visible geometry and excluded defect pixels are supplied in the separate export. They are not full-frame pixel parity results. Raw maps and transformed evaluator masks are retained for independent recomputation.

Under the recorded configurations, the upstream reference has higher image AUROC than the adapted primary in 8 of 8 groups. This comparison changes backbone, preprocessing, memory size and coreset procedure together; it cannot attribute the difference to one component or establish a universal method ranking. The fixed candidate remains the reported primary rather than being replaced by a test-selected model.

For capsules development, the reference crop excludes 165,085 of 411,973 annotated native defect pixels (40.1%), under the declared pixel-center geometric visibility convention. This is a coverage loss, not a count of model misses; nearest-neighbor resampling losses are recorded separately. The full source image label is retained for image-level scoring.

For capsules final, the reference crop excludes 61,994 of 404,371 annotated native defect pixels (15.3%), under the declared pixel-center geometric visibility convention. This is a coverage loss, not a count of model misses; nearest-neighbor resampling losses are recorded separately. The full source image label is retained for image-level scoring.

The reference uses pinned upstream code, WideResNet50-2 ImageNet V1, layer2 and layer3 features, 1024-dimensional embeddings, exact FAISS 1NN and native 224 segmentation maps [5]. A disk-backed feature assembly wrapper is explicitly distinguished from standard fit orchestration for the two larger pools. Its four-normal parity check is narrow; full-run identity is not assumed. Image p95 and pixel p99.5 normal thresholds remain frozen. Calibration maps are replayed and must reproduce the existing pixel threshold exactly before held-out prediction. GT uses nearest-neighbor resize with matching crop geometry; native geometric and resampled defect coverage are recorded separately. FAISS squared-L2 scores cannot be compared directly with OpenCV L2 scores.

## Runtime and provenance

| Environment | Variant | Measured sequential N | Handler p50 ms | Handler p95 ms | Peak RSS MiB |
| --- | --- | --- | --- | --- | --- |
| Shared local HTTP | v1 | 300 | 303.4 | 574.2 | 225.0 |
| Shared local HTTP | v2 | 300 | 346.2 | 738.3 | 323.5 |
| Dedicated Fargate HTTP | v1 | 300 | 963.3 | 1070.5 | 307.0 |
| Dedicated Fargate HTTP | v2 | 300 | 1104.7 | 1256.2 | 441.7 |

The dedicated Fargate task used the recorded one-vCPU/two-GiB configuration and stopped successfully. Each local/dedicated comparison retained 820 matched successful request/sample/inspection records, including warmups, repeated sequential inputs and a finite concurrency-two probe. Dedicated handler p95 rises by 17.35% and peak RSS by 43.90% for the candidate. Configured CPU allocation is not measured utilization. Local timings include competing training/evaluation work and cannot establish isolated hardware capacity.

The public deployed v1 completed 10 warmups and 100 measured uploads in a retained segmented run. All 110 IDs correlate with CloudWatch events. Collector assertions connect submitted image bytes and bank hashes to the IDs; the older deployed log lacks image and bank SHA fields. Its measured HTTP p50/p95 are 3904.4 / 4722.9 ms. This paced public profile measures neither capacity nor candidate performance. Stage spans may overlap; percentile summaries must not be added.

The retained AWS source archive matches 17 current frozen application modules, 8 primary/detail profile files and 100 fixture byte sequences. The orchestration profiler has a separately retained local revision for output locking and diagnostics; that difference is not an application or CV method change. The archive and source-identity receipt identify what was actually measured.

## Limitations and release interpretation

The study covers selected published categories and custom partitions, with uncertain physical independence and no new factory validation. The reused replay informed earlier development. The classical comparison also changes internal resolution. Reference center cropping changes evaluated pixel coverage. Resized GT and crop-connected components require their own denominators. Synthetic capture perturbations and dependent stress copies cannot validate retake routing on new photographs or estimate a factory failure rate.

The active-trigger criterion is incomplete, reviews remain unresolved, and false-alert costs are category-specific. Supplemental controls describe equal logical budgets but reuse batch tile outputs; runtime belongs to the separate integrated API measurements. Accuracy work, cache-enabled fitting, reference CPU inference, loopback HTTP and public-network timings have distinct scopes. No causal advantage is assigned to unused registration or second-view components.

The candidate stays local. This conclusion follows from the recorded weaknesses and operational costs without choosing a different test-winning arm. Further deployment requires evidence for the affected categories and workflow, with false clears, alerts and review workload judged together. The current work makes no novelty, factory-readiness, official-parity or superiority claim.

## Reproduction and correction record

The fresh complete application and benchmark regression after reporting exports passed 114 tests with the actual weights and dataset environment enabled. The retained log identifies this run. It is not a sum of earlier complete and focused test counts. Test success verifies its software scope; image, pixel-map, runtime and document-render checks retain their own receipts.

A source/model/manifest freeze precedes the first candidate accuracy case. The accompanying source snapshot records the exact hashes used for this manuscript, including the image oracle, corrected metric audit and separate runtime receipts. Image identities, saved predictions, model banks, masks and maps remain distinct evidence. Earlier reports, paper and slides are preserved with a correction notice for historical AU-PRO; recomputation uses unchanged saved maps rather than silently retraining a baseline.

## Conclusion

The predeclared candidate changes the balance between confirmed defects, automatic false clears, false alerts and reviews. Gains on the older replay coexist with weaker final macro ranking, a capsule failure case and higher resource costs. Corrected localization metrics and explicit provenance improve the reliability of this evaluation, with complete reference and map verification recorded separately in the evidence package.

## References

[1] K Roth et al. Towards Total Recall in Industrial Anomaly Detection. CVPR 2022. https://arxiv.org/abs/2106.08265

[2] Y Zou et al. SPot the Difference Self Supervised Pre training for Anomaly Detection and Segmentation. ECCV 2022. https://arxiv.org/abs/2207.14315

[3] K He et al. Deep Residual Learning for Image Recognition. CVPR 2016. https://arxiv.org/abs/1512.03385

[4] Amazon Web Services. Visual Anomaly VisA. Registry of Open Data on AWS. CC BY4.0. https://registry.opendata.aws/visa/

[5] Amazon Science. PatchCore inspection source, commit fcaa92f124fb1ad74a7acf56726decd4b27cbcad. https://github.com/amazon-science/patchcore-inspection

[6] D Muhr. pyaupro version 0.1.11, independent PRO reference curve and utility source. https://github.com/davnn/pyaupro

[7] Amazon Science. VisA metric source, commit 2a692ab575001cbde74d402d897a7286086c6199. https://github.com/amazon-science/spot-diff/blob/2a692ab575001cbde74d402d897a7286086c6199/utils/metrics.py
