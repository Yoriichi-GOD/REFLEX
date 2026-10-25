# REFLEX improvement protocol — 24 October 2026

Authorized scope: improve the detector after the completed baseline evaluation, then rerun benchmarks. Existing baseline reports and submission archive remain immutable.

Baseline archive SHA256: `1503ceb71c4ccd271928b806cc4980ee46110b515edebfbd9078c905a9230b90`.

## Hypotheses and frozen choices

The spatial median/MAD reference confuses pose changes with anomalies and misses local defects. Compare patches to a location-independent memory of normal pretrained visual features. Use ImageNet ResNet50 from the official ONNX model zoo through OpenCV 5 DNN; never substitute random weights. This is an adapted nearest-patch detector, not an official PatchCore reproduction.

Candidate v1 choices, fixed before test replay: full-image aspect-preserving letterbox to 256 square; RGB ImageNet normalization; stage2/stage3 local 3x3 averaged features; concatenate after bilinear grid alignment; seeded sparse random projection to 128 dimensions; deterministic per-image patch sampling; greedy farthest-point coreset of at most 4096 patches; Euclidean nearest-normal distance; max patch image score; bilinear map reconstruction and Gaussian sigma4 smoothing. No test-label-based threshold search. CPU execution with four OpenCV threads.

Normal train membership: same seed20261023 80/20 fit/calibration split as baseline. Reserve the last seed-shuffled 10% of fitting normals for development validation; all coreset fitting uses the remaining normals. Calibration uses only the original 20% normal calibration group. Normal image threshold is its 95th percentile (higher); pixel threshold is its 99.5th percentile. The development split checks normal rejection and deterministic rotated normals; painted defects are development probes only and never reported as real defects. No validation or calibration images enter the memory bank.

## Acceptance and limitations

Run unit/regression tests and development checks before freezing code/configuration hashes and rerunning the 350 official candle/cashew test cases. Report AUROC/AP, thresholded confusion matrix, precision/recall/F1/FPR, pixel metrics, latency, and perturbation results. Accept only measured gains; preserve regressions. A higher recall caused solely by more normal false alarms is insufficient. Tests already informed the diagnosis, so the rerun is reused-test development evidence, not a new blind generalization estimate. pcb1 and external dataset coverage remain separate gaps.

Do not use the old crop-to-full-spatial-bank policy with the new features. Only offer the candidate in the application after verification. Do not claim AWS latency for the changed model until it has run on AWS. The deployed synthetic profile and prior AWS measurements describe the original detector.

## Definition of done

1. Verified pretrained weights and hash, deterministic fit/calibration/development manifests.
2. Correct preprocessing, coordinates, memory search, tamper checks and category isolation covered by tests.
3. Completed real benchmark replay, rotation/other robustness checks, all per-case predictions and timing logs.
4. Comparison report and failure gallery; no silent replacement of original results.
5. Working local application integration and regression tests; explicit remaining gaps.
