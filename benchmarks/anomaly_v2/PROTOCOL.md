# REFLEX v2 predeclared improvement protocol

Written before v2 training or test inference, 24 October 2026.

## Scope and guardrails

The user authorized all improvements listed in reports/diagnosis_20261024. Preserve the deployed v1 and original reports, model banks, source freeze, and submission materials. Add versioned v2 code/models and local profiles. Do not select a candidate by its reused candle/cashew test score. No test masks or labels enter fitting, calibration, ROI selection, quality checks, or inference. Ground truth is evaluator-only after prediction.

Existing 350 candle/cashew cases are development replay forever. Additional legitimately acquired capsules/chewinggum are fresh-to-REFLEX categories, not new candle/cashew captures. A data owner will freeze hash-separated development/final membership and report missing physical-item/lot identifiers. All thresholds use normal calibration only; no tuning on any published anomaly test subset. Real development labels, if acquired, are used only for diagnosis after this protocol freeze. No customer or physical multi-view claims are allowed.

## Fixed experiments

Use verified ImageNet ResNet50 ONNX weights and existing OpenCV5 stage2/3 feature graph. All full-frame arms use the same 648/324 fitting and 180/90 calibration normals as v1; reserved 72/36 development normals stay outside fitting. New categories use their own disjoint normal memberships. No normal calibration outlier removal.

1. V1 frozen reference, unchanged.
2. `dense128_max`: 96 spatially balanced valid patches per fit image, 4096-patch greedy coreset, seeded128D projection, max-patch image score. This isolates denser normal coverage (sampling/padding consistency are disclosed together).
3. `dense512_max`: identical to arm2 except512D projection. Preserve memory count and memberships.
4. `dense128_top4`: same fitted memory as arm2; mean of the top4 valid patch distances, independently calibrated p95 normal threshold.
5. **Predeclared primary** `dense128_region`: same fitted memory; maximum local3x3 mean over valid patch centers, independently calibrated normal p95 image threshold. No ground-truth/object crop. Smoothing sigma1 for candidate localization; report sigma4 comparison using the same raw map.
6. `dense128_pose`: arm2 fitting also embeds a deterministic+7degree rotated version of every normal fit image; masks/labels never used; independent thresholds recalibrated. Derived fit images are not new real images.
7. `detail128`: separate scale-specific normal bank from four overlapping corner tiles, each62.5%width/height;24 balanced patches per tile;128D,4096memory. One chosen tile and one seeded random tile per evaluation image provide matched separate controls; no arbitrary crop reuses the full-frame threshold. Chosen tile maximizes full-frame map mean over its source rectangle. Chosen and random policies each get their own normal calibration p95 threshold. A fixed full+all4-tile comparison is an explicit higher-budget arm.

Base seed20261024. Repeat dense128/512 memory construction with seeds20261025 and20261026 as a stability check; report all, never best-seed-only. Normal development ranking/diagnostics do not authorize claiming blind candle/cashew generalization. The primary method is fixed above and all variants remain reported if primary fails.

## Review/agent rule

Automatic defect boundary is normal calibration p95. A lower PASS boundary is selected only among calibration p80,p85,p90,p95 using reserved normal development canonical and+7degree normal scores: select the lowest quantile whose extra review fraction above the existing defect boundary is at most10% in both normal variants. If none qualifies, use p95 (no new review band). Report actual false alerts, review burden, coverage, false clears and binomial intervals separately.

For a quality-suitable score in the review band, make at most one chosen detail-tile model call, using its separately fitted/calibrated normal reference. Above its p95 boundary, return DEFECT_FOUND with real tile evidence; otherwise remain NEEDS_REVIEW. Never turn inconclusive second evidence into an automatic PASS. Quality flags request retake/review. Do not count review as a correct detection. Forced chosen/random one-tile controls on all350 cases quantify second-look evidence under equal calls and source pixel budgets. Report the smaller actual active-trigger subset separately, including any failure to reach30 triggers.

## Quality and localization

Add a normal-calibrated capture suitability module without changing legacy quality.py. Validate internal occlusion/field-of-view checks on disjoint normal development and dependent derived occlusions at multiple positions/sizes; validate canonical defect false retakes after candidate freeze. No invented real-capture quality labels, broad wrong-profile accuracy or universal segmentation claim. Preserve negatives and unsupported checks.

Report candidate sigma1 versus4 and normal pixel calibration percentiles99.5/99.75/99.9 on the same max-side256 evaluation grid. Primary localization uses sigma1 and normalp99.75. Retain native-resolution masks/maps for separate review. Do not select localization threshold on test IoU.

## Verification and acceptance

Run legacy tests before edits (41passed), then unit tests for valid padding exclusion, balanced sampling, deterministic fitting, integrity/metadata, scoring, review boundaries, tile coordinates, independent scale calibration, bounded tool calls, API/export and category isolation. Run actual weights integration tests and regression suite. Preserve13frozen scientific source hashes.

Evaluate every fixed arm on the same350reused cases, with labels/masks accessed after prediction. Report image AUROC/AP, threshold confusion, decisions/reviews, pixel AUROC/AP/precision/recall/IoU/Dice/AU-PRO, component and area results, latency, peak process memory and fit seconds. Nine stress families must remain dependent copies; include capture routing as well as raw scores. Official PatchCore is a separate reference attempt, never a name for these adaptations.

Fresh-category final scoring occurs only after source/model/configuration freeze. No tuning after final access. No claim of defect gains from extra abstention or much higher normal false alerts. Replacing public v1 requires a concrete measured release report and deployment coordination; candidate models can remain local if that gate fails. Changed-model AWS performance must measure actual changed code/input with matching resource identity, concurrency and request correlation, never borrow v1/synthetic timings. Credentials/cost/plan/runtime blockers are documented, not bypassed.

## Definition of done

All authorized feasible experiment arms implemented, tested and executed; every run and failure retained; fixed primary clearly identified; fresh final boundaries enforced; real controls and latency measured; report, gallery, machine-readable results and reproducible commands saved; local app integration verified with candidate profiles. Promote only supported results. External dataset/capture/runtime/AWS blockers have exact logs and completed unaffected work.

## Additional-category execution addendum (before any v2 test inference)

Publisher-verified capsules/chewinggum were acquired by the separate data owner. All257401856selected archive bytes match the publisher; whole-archive integrity is not claimed. Prepared data live in reflex-data/reference_20261024/prepared; manifests_v2 preserves391/108/43capsule fit/calibration/train-development normals and326/91/36chewinggum normals. Each category has a stratified published-test development/final half, with final80/75images. Neither half selects parameters or thresholds; no physical lot IDs are available.

Run the same predeclared v2 arms/seeds on these categories. Fit an additional unchanged v1 patch-memory baseline on identical new-category normal memberships. Evaluate development and final partitions separately only after all model/source hashes freeze, without tuning between them. Any pcb1 acquisition receives a separate manifest/protocol and no retrospective membership edits. A feature cache stores actual pretrained float32 embeddings keyed by decoded input pixels, shape and feature-graph hash; it contains no labels or decisions. Cache-enabled experiment timings are not production latency. Separate uncached CPU and AWS profiles measure actual execution.

Suitability clues remain warning-only; their6722-row stress record does not supply independent physical capture validation. Keep automatic routing flags empty. Preserve the66-test regression checkpoint. All older source freezes, models, evidence and delivered PPT/paper files remain unchanged.

## PCB1 addendum (before PCB1 fitting or test inference)

A new complete public VisA archive was acquired with stable ETag and byte-range verification. LocalfullSHA2562eb8690c803ab37de0324772964100169ec8ba1fa3f7e94291c9ca673f40f362 is locally computed; publisher-independent SHA is unavailable. Separate PCB1 manifests at reflex-data/reference_pcb1_20261024 preserve651fit/181calibration/72normaltrain-development and100development/100final images (each50normal50defect). Same fixed v2 arms and unchanged v1 method baseline use these exact normal memberships. No PCB1 test labels tune scoring, thresholds, review or models. The final split stays sealed until source/model freeze. All initial source/manifest freezes and failed attempts remain retained.
