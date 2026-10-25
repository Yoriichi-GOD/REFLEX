# REFLEX and pinned upstream PatchCore reference

All five reference fits, all eight reference evaluations and the copied final evidence bundle are complete. This reader independently rechecked every copied file fingerprint and paired source-image membership. Neither test results nor this comparison select a new release.

| Category / population | N | V1 AUROC | REFLEX primary AUROC | Reference AUROC | Primary detected / false alerts / reviews | Reference detected / false alerts |
|---|---:|---:|---:|---:|---:|---:|
| cashew / replay | 150 | 0.9476 | 0.9600 | 0.9746 | 77 / 0 / 0 | 83 / 2 |
| candle / replay | 200 | 0.9005 | 0.9566 | 0.9906 | 78 / 6 / 4 | 91 / 5 |
| capsules / development | 80 | 0.7027 | 0.6680 | 0.7160 | 14 / 2 / 0 | 18 / 4 |
| capsules / final | 80 | 0.7233 | 0.6713 | 0.8000 | 16 / 1 / 0 | 26 / 1 |
| chewinggum / development | 75 | 0.9680 | 0.9912 | 0.9928 | 49 / 1 / 3 | 47 / 0 |
| chewinggum / final | 75 | 0.9840 | 0.9736 | 0.9840 | 48 / 4 / 1 | 47 / 1 |
| pcb1 / development | 100 | 0.8932 | 0.9112 | 0.9988 | 38 / 6 / 7 | 49 / 1 |
| pcb1 / final | 100 | 0.8488 | 0.8780 | 0.9644 | 41 / 9 / 10 | 48 / 5 |

## Interpreting the reference

The reference ranks images better than the fixed REFLEX primary in each measured category/population group. This experiment changes several components together: WRN50 backbone, 1024-dimensional embedding, full ordered normal patch pool, 10% approximate greedy coreset, squared-L2 FAISS scoring and center-crop224 preprocessing. It does not identify which component caused the difference. A higher score rank does not guarantee better decisions at separately calibrated thresholds.

Cashew, capsules and chewinggum use standard upstream fitting orchestration. Candle and PCB1 use a labeled disk-backed assembly wrapper after an original allocation failure. The wrapper retains upstream feature, sampler and search components. A four-normal byte-parity check supports the assembly implementation on that small fixture; full-run byte equivalence is not asserted. All failed and interrupted attempts remain in the bundle.

The reference is a local CPU baseline with much larger memory banks. Its prediction-only timing excludes image read/transform and competes with other host work. It is not a measured deployable AWS replacement. The candidate release remains on hold.

## Crop-only localization

| Category / population | Crop pixel AP | Crop AU-PRO | Native defect pixels retained | Fully excluded defect images |
|---|---:|---:|---:|---:|
| cashew / replay | 0.6157 | 0.9269 | 2525551 / 2530212 | 0 |
| candle / replay | 0.2543 | 0.9612 | 403990 / 405291 | 0 |
| capsules / development | 0.5456 | 0.8439 | 246888 / 411973 | 5 |
| capsules / final | 0.7806 | 0.8757 | 342377 / 404371 | 3 |
| chewinggum / development | 0.4501 | 0.8101 | 663933 / 663936 | 0 |
| chewinggum / final | 0.4878 | 0.8383 | 607475 / 607475 | 0 |
| pcb1 / development | 0.8997 | 0.9295 | 693479 / 695226 | 0 |
| pcb1 / final | 0.8895 | 0.9219 | 703617 / 703688 | 0 |

Crop pixel scores have a different denominator from REFLEX full-frame scores. No omitted area is filled as normal. The capsules final center crop retains only 84.67% of annotated native defect pixels; development retains59.93%. Pixel AP/AU-PRO cannot be used as a direct full-frame improvement claim.

Corrected AU-PRO uses exact float32 score events, eight-connected regions, equal region weights, all normal pixels in the evaluation crop and a linear clip normalized at FPR0.30. Independent curve checks passed. Publisher implementation byte parity remains blocked by the recorded archive HTTP404. Historical custom AU-PRO is invalid for comparison.

## Evidence

Canonical reference bundle: `C:\Users\nrgen\.codex\scratch\reflex\reports\reference_20261024\final_bundle_20261024T223543Z`.
The bundle contains original model indices/parameters, normal calibration maps, every reference score map and crop mask, coverage geometry, per-case outputs, source/config freezes, audits and original failures. The linked export contains all eight image/crop tables. All860source identities match the candidate by category, population, imageSHA and label.

Candle/cashew remain reused development replay. New-to-REFLEX category development/final partitions contain public VisA cases. No physical-part or lot independence, factory readiness, official leaderboard equivalence or state-of-the-art claim follows.
