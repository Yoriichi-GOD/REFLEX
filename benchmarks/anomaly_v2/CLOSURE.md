# REFLEX v2 study closure — 25 October 2026

Decision: **HOLD_CANDIDATE_LOCAL**. All authorized feasible fixed experiments, reference fits, map replays and review artifacts are complete. This closes the study and evidence delivery; it does not certify factory suitability or promote v2 to the live service.

## What was verified

| Requirement | Outcome and evidence |
|---|---|
| Real data and provenance | Five legitimate VisA categories, local archive hash and frozen source/membership hashes. Published cases; physical part/lot independence unknown. |
| Normal-only fit/calibration | Separate fixed memberships; labels/masks read after inference. All 143 source/model/manifest freeze hashes match. |
| Fixed method comparisons | 88 method/group rows over 860 distinct cases; 9,460 repeated-method predictions independently reproduced. Every arm and seed retained. |
| Baseline strength | Same-case OpenCV baseline and unchanged v1; pinned WRN50 upstream reference across eight groups. Classical legacy grid differs in resolution. Reference has higher image AUROC in all eight groups, under different configurations. |
| Agent controls | Eight groups; 40 selective rows and 24 fixed-budget fusion rows. Chosen/random/ROI-off share false-clear sets. Review contribution separated from actual detections. Active trigger sufficiency NOT MET. |
| Localization and robustness | 48 fixed localization rows; 45 dependent robustness rows. All 88 arm maps and 13 control/stress groups replayed and reproduced. No new independent images from transforms. |
| Historical metric correction | Original AU-PRO invalid for comparison; unchanged baseline maps rescored with corrected exact events. Analytic/oracle checks passed; publisher byte parity BLOCKED by retained HTTP404. Originals preserved. |
| Regression | Latest full suite:114 passed,13 deprecation warnings,21.21sec. Separate focused reporting runs:5 passed. Real weights/data enabled. Earlier harness failures retained. |
| AWS execution | Dedicated and local runs each820 correlated successful requests; public v1 profile110 (100 measured). Actual code/bank/input identity checked. Dedicated task stopped exit0. No per-task CPU or capacity claim. |
| Visual evidence | All860 real-case panels and46 actual detail crops; nine graphs in PNG/SVG/PDF. File/data checks passed. Browser interaction BLOCKED by Work local-browser setting; no bypass. |
| Presentation and paper | Six-slide pitch,37-slide editable evidence deck,17 embedded chart workbooks; seven-page paper,four-page supplement,one-page correction; editableDOCX/PPTX and all43slide/all12page previews reviewed. Native PowerPoint rendering remains untested. |
| Release/publication | Candidate hold; live v1 preserved. No deployment or public submission performed. Team details, presenter/video, public package link and submission receipt remain human work. |

## What improved and what did not

On reused candle/cashew cases, v1 detected112/200 defects and falsely cleared88. Primary v2 detected155, falsely cleared41 and left4 defect reviews unresolved; false alerts rose5→6/150 normals. This is exposed replay, not blind generalization.

On the new-category final partition, detected defects rose92→105/150, but false alerts rose9→14/105 normals, with11 unresolved reviews (three defects,eight normals). Equal-category image AUROC fell0.852044→0.840978. Capsules final still misses34/50 defects. Do not call this a clean benchmark win.

The pinned upstream reference has higher image AUROC in8/8groups. Its WRN50 features,10% coreset,squared-L2 scoring and resize256/center-crop224 protocol differ together. This experiment cannot attribute the gap to one component. Its crop-only pixel metrics exclude source pixels; capsules coverage is59.93% development and84.67% final, so never equate those pixel scores with REFLEX full-frame localization.

Dedicated AWS full-handler p95 rose1070.469→1256.220ms (+17.35%); peak RSS321,888,256→463,192,064bytes (+43.90%). Same fixtures and configured1vCPU/2GiB. Actual per-task CPU was not measured. Local figures share the development host with other jobs. Public pacing reflects the upload guard, not capacity.

## Boundaries and next decision

No fresh factory captures, independent lot identifiers, genuine new-view/retake study or validated universal quality routing are available. No final-test seed/arm/threshold winner is promoted. Future improvement needs a separately declared protocol and new independent validation. Fresh-machine relocation was not exercised; absolute manifest paths and external assets require remapping as documented in the reproduction guide. MVTec/LOCO/MPDD,12-category expansion,PaDiM/EfficientAD and Real-IAD are NOT RUN in this study; they add no claimed result. Optional unavailable/restricted data is not replaced with synthetic data.

The supplied96-image synthetic kit remains a separate regression population; historical audit and per-case results are retained in reports/data_audit.json and reports/synthetic_qa. Their scores never enter VisA tables. The public real-photo UI remains the verified v1 candle/cashew release. Its earlier browser evidence does not validate the newly generated offline gallery controls.

## Evidence entry points

- report/REPORT.md and all full-precision CSV tables
- report/REFERENCE_COMPARISON.md and REFERENCE_VERIFICATION.json
- report/gallery/index.html (all real cases; browser-interaction limitation above)
- accuracy-verification/VERIFICATION.json and ALL_IMAGE_RESULTS.csv
- supplemental_maps/status.json and supplemental_control_maps/status.json
- policy-contribution/FINDINGS.md
- local-http-profile-r4, fargate-profile and aws-current-real-profile verification receipts
- freeze.json, regression-after-report-exports.log and CLOSURE.json
- ../../submission-materials/20261025-v2/README.md (reviewed delivery)
