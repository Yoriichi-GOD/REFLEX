# REFLEX model card

The expanded frozen-model benchmark, including 256-grid pixel metrics, AU-PRO, ablations, robustness, challenge inputs, and the synthetic-only AWS profile, is in [`../reports/FINAL_BENCHMARK_REPORT.md`](../reports/FINAL_BENCHMARK_REPORT.md).

## Model identity

- **Current profile:** `synthetic_machined_plate`
- **Model mode:** `opencv_normal_bank`
- **Version:** `reflex-opencv-normal-bank-1`
- **Pretrained backbone:** none
- **Verified runtimes:** OpenCV 5.0.0 on the local CPU and in the Sydney AWS demo
- **Intended use:** triage unusual pixels in a fixed synthetic component scene; show relative evidence and request review/capture when image quality is inadequate.
- **Not intended for:** safety certification, autonomous rejection, physical crack measurement, other classes without a fitted profile, or real-factory claims.

## Data and fitting

The default bank is fitted from 40 seeded synthetic normal images and calibrated on 12 different seeded synthetic normals. It stores per-location feature medians and MAD scales. Feature channels are Lab lightness, local lightness residual, absolute Laplacian, Sobel magnitude, and Lab chroma. The 120×90 feature grid is spatially indexed; the method expects aligned scene geometry. This is an OpenCV normal-reference baseline, not an implementation of official PatchCore.

Thresholds: image score is the 99.5th percentile of the smoothed map; image threshold is the 95th percentile of the 12 normal calibration-image scores. Pixel threshold is the 99.5th percentile of normal calibration-map pixels and is treated as a finite-sample heuristic. Scores are distances, not probabilities.

## Measured results

Current synthetic holdout: 12 normal and 20 defect fixtures, with five generated change types. Image AUROC 0.9875, precision 0.947368, recall 0.9, F1 0.923077 at frozen threshold; TP 18, FP 1, FN 2, TN 11. Synthetic pixel AUROC 0.998488; pixel IoU 0.291960. These synthetic metrics describe only generated fixtures.

Separate offline fits were evaluated on two official VisA one-class categories using disjoint fit/calibration normals and untouched official test cases. This is the same OpenCV baseline, not the default app profile:

| VisA class | Test normals / anomalies | Image AUROC | Precision / recall / F1 | False clears |
|---|---:|---:|---:|---:|
| candle | 100 / 100 | 0.7579 | 0.8000 / 0.1600 / 0.2667 | 84 / 100 |
| cashew | 50 / 100 | 0.5988 | 0.6250 / 0.0500 / 0.0926 | 95 / 100 |

These are poor detection results; this baseline is not ready for real inspection. The full VisA archive checksum was not verified. Dataset hashes, exact splits, pixel-level metrics, and error examples are in [`EVALUATION.md`](EVALUATION.md).

The complete pass reported pixel AUROC/AP and AU-PRO@0.30 on an aspect-preserving max-side-256 evaluation grid. Agent full-crop, static, matched random-crop, and quality-gate-off variants produced identical decisions on all 350 canonical test images. Only 28 images triggered native crop inspection, below the 30-case minimum for a stable random-crop comparison. Eight deterministic image perturbations and a wrong-category model were scored separately from the canonical table. See the linked report for every metric and per-case result.

The agent branched on 19 of 32 cases but did not change final decisions against a score-threshold-only baseline. Its measured added policy time averaged 1.0477 ms. This does not demonstrate reduced error rate.

## Known failure modes and limits

Two generated discoloration cases fell below the image threshold, and one normal generated fixture crossed it. Normal brushed-metal lines can create bright heatmap bands. Pixel localization is imprecise at the chosen threshold: IoU was 0.292. A changed camera position, illumination, scale, object, background, or manufacturing variation is outside the fitted distribution. Low focus is a heuristic quality flag, not a calibrated quality probability.

MVTec fit/evaluation scripts exist but were not run because the official download page reported downloads temporarily unavailable during this pass. The required PatchCore comparison remains blocked: PyTorch import was denied by Windows Application Control and WSL access was denied, so no pretrained PatchCore result is reported. No physical bench photos were used. Offline VisA profiles are not deployed. AWS profile status and limits are in the linked report. See [`DATA_LICENSES.md`](DATA_LICENSES.md) and [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md).
