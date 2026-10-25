# REFLEX Metric Correction and Evaluation Update



This notice corrects the historical custom AU-PRO calculation in the earlier REFLEX report, paper and slide deliveries. Those files remain historical evidence. Their AU-PRO values and figures must not be used for comparison until replaced by a separately identified corrected recomputation. Other metrics are not invalidated without their own evidence.

## Metric defect and correction

The historical scorer collapses repeated false-positive-rate points to their largest PRO value. It can erase the lower endpoint of a vertical jump and assign partial area where no annotated region was recovered. A reverse-ranked analytic map exposes the defect. The corrected version retains unique-score transitions, merges score ties only, preserves vertical endpoints and linearly clips trapezoidal area at maxFPR 0.30 before normalization.

| Synthetic fixture | Historical AU PRO | Corrected AU PRO |
| --- | --- | --- |
| perfect | 1.0000 | 1.0000 |
| reversed | 0.1500 | 0.0000 |
| constant | undefined | 0.1500 |
| unequal_regions | 0.5750 | 0.5000 |
| diagonal_component | 0.5750 | 0.5000 |

The corrected method uses eight-connected components, equal region weights and a global normal-pixel denominator including normal source images. Constant scores produce diagonal tie interpolation under the declared convention; missing positive regions or negative pixels produces undefined. The independent pyaupro reference curve agrees with the literal threshold oracle, but its convenience AUC helper pads horizontally rather than linearly clipping a crossing segment. These integration conventions must not be conflated.

The original metric source, failure fixtures, corrected source hashes, package snapshots, regression logs and validation protocol are retained. The correction passed 39 focused tests; the reference environment passed 52 tests including those 39 and 13 crop/calibration/artifact checks. These are separate verification runs, not an additive test count. The publisher evaluation archive returned HTTP 404, so official publisher-byte parity remains blocked.

## Updated evaluation result

The candidate stays local. On the additional-category final partitions it confirms 105 rather than 92 of 150 defects, while false alerts rise from 9 to 14 of 105 normals and 11 cases remain unresolved. Final macro AUROC falls from 0.85204 to 0.84098. Dedicated AWS handler p95 and peak RSS rise by 17.35% and 43.90%. The complete paper preserves all eight groups, all fixed arms and seeds, and the weak capsule result. These findings do not establish factory readiness, novelty or official parity.

A post-evaluation descriptive audit of unchanged outcomes finds identical false-clear case-ID sets for review-only, chosen-crop and random-crop paths in every group. The review band removes those automatic passes; crop choice does not further reduce them. Across 46 executed active cases (29 defective and 17 normal), chosen detail resolves 17 additional true alerts and 4 false alerts relative to review without ROI. Random detail resolves 12 true alerts and 2 false alerts. Review-only leaves 46 unresolved, chosen 25, and random 32; all three retain 127 automatic false clears in the execution audit. These cross-population totals audit controller behavior, not pooled generalization or a superiority test.

## Use with earlier deliveries

Attach this notice when circulating earlier material. Replace historical AU-PRO comparisons only with the versioned corrected artifacts and keep the original values accessible. The updated method remains a local candidate. The eight population groups and all fixed arms/seeds remain separate. Completed reference results and map-verification receipts accompany the updated paper. Reference pixel metrics remain crop-only, with excluded defect coverage disclosed separately.

## Evidence identities

Candidate source/model/manifest freeze SHA256 62d81cbc0e38f5fe158cd9506cadbdffe97ae24b593b4289aca510c9c60e6dbb. Corrected metric SHA256 9eeaf936ad2ab221cb0abb819048b160bdcb9f3ef2c18c21a74996ccba5f8a63. The manuscript source manifest retains exact paths, byte hashes and snapshot copies for all numerical authorities.
