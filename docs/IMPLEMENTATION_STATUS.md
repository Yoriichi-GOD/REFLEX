# Additive Safety Station checkpoint — 25 October 2026

The extension has separate current evidence in [STATUS.md](../STATUS.md): 138 integrated Python tests passed, source-only checks passed, and all 143 frozen experiment files remain unchanged. Physical procedural video, rendered-browser/camera and extension AWS gates remain open. The study checkpoint below predates the extension and its counts describe that separate completed study.

---

# Current improvement status - 25 October 2026

Last evidence refresh: 2026-10-25T02:59:29.486203+00:00. Historical deployed-v1 status follows below.

- All five candidate categories, nine fixed arms, five classical baselines and three additional unchanged-v1 fits completed before the frozen evaluation.
- The separate image oracle verified 88 method/group rows over 860 unique population cases. All 143 frozen files match. The latest full regression passed 114 tests with 13 deprecation warnings; five focused reporting checks passed separately.
- All eight accuracy, all eight detail-control groups and all 45 derived robustness configurations completed. All 88 arm-map groups, 13 control/stress map groups and the complete upstream reference bundle are verified.
- Local and dedicated AWS service profiles each verified 820 HTTP200 correlations. The segmented public v1 real-image profile verified 110 correlations, including 100 measured requests. Corrected actual worker memory and separate HTTP/backend spans are retained.
- Historical AU-PRO in earlier reports/paper/PPT is invalid for comparison. The corrected independently checked metric recomputes unchanged legacy maps. Publisher byte parity remains blocked; other measured metrics are assessed separately.
- V2 remains a local candidate. Better replay recall does not erase weak capsules results, increased normal false alerts in other categories, higher runtime/memory, or the lack of independent physical-lot validation.

Current numbers and limits: [verified checkpoint](../reports/improvement_v2_20261024/VERIFIED_PROGRESS.md). The live release and original submission materials remain preserved.

---
# Implementation status

Status values distinguish code present from evidence observed. `tested` does not mean deployed.

| Feature | Status | Evidence / boundary |
|---|---|---|
| OpenCV 5 runtime guard and health endpoint | tested | Runtime reported `5.0.0`; startup rejects a non-5 major version. |
| Synthetic normal-only profile | tested | 40 normal train images; 12 separate normal calibration images; model mode `opencv_normal_bank`. |
| Image decode, dimensions, MIME, grayscale, alpha, 16-bit, EXIF orientation | tested | Unit/API tests; 12 MB, 4096 px edge, and 20 MP guards. |
| Quality flags, foreground proposal, heatmap, region coordinates | tested | Core checks and live API integration tests. |
| Native source-pixel crop tool and bounded agent branch | tested | Scratch fixture triggers `inspect_crop`; source dimensions, score, edge density, and crop evidence are computed on the crop. |
| Low-quality retake request and actual retake upload | tested | Blurred fixture requests a capture; `/continue` ingests the newly supplied image and creates a linked inspection. |
| ECC affine alignment and registered difference | tested | Translated-image alignment and API artifact test pass; weak/size-mismatched registration is refused. |
| Review record separate from model result | tested | SQLite review survives a subsequent GET; the stored model decision is unchanged. |
| JSON/HTML report and image artifacts | tested | API export and source/heat/overlay/mask/ROI artifacts return successfully. |
| Responsive inspection UI | tested | Live local browser checks covered desktop and 390 px mobile layout, image layers, reference alignment/difference, zoom, retake, review, and export. A live AWS scratch-result screenshot is saved in `demo/screenshots/`. |
| Synthetic holdout evaluation | tested | 32 fixed synthetic holdout cases; exact counts and metrics are in [`EVALUATION.md`](EVALUATION.md) and `results/`. |
| VisA original spatial bank | tested; preserved | Official one-class split, candle (200 test cases) and cashew (150 test cases); original recall0.16/0.05. Original reports and archive remain unchanged. |
| VisA patch-memory improvement | tested locally | Image AUROC0.9005/0.9476, recall0.42/0.70, normal FPR0.03/0.04. 350 real cases plus3,150 derived perturbations. Reused official test evidence; normal-only fitting/calibration with reserved development normals. Full report: `reports/improvement_20261024/REPORT.md`. |
| Real-image profile/API integration | tested locally and on AWS | Saved-model reload, score agreement, matching evaluation panel, category rejection, quality/human-review branches, explicit category trace. Six live AWS real-image smoke cases match the frozen scores within0.000001. New model does not use the old crop confirmation or claim reinspection gain. |
| Real-photograph gallery and comparison | deployed and verified | Six licensed VisA photographs; per-request candle/cashew selection; Original / Heatmap / Overlay together. All six original decoded images match source pixels. A public-browser gallery click loaded all three panels. Evidence: `reports/real_demo_20261024/RELEASE.md`. |
| Generic MVTec/VisA fit/evaluate scripts | implemented | Fit/calibration use disjoint normal training images only; test labels and masks are read only by evaluation. VisA scripts were run. MVTec was not run because its official download page currently reports the dataset download unavailable. |
| Pretrained nearest-normal patch model | tested locally and on AWS | OpenCV5 DNN, verified ResNet50 stage2/3 features, deterministic projection/coreset and exact L2 search. Official WideResNet PatchCore remains blocked by the host PyTorch DLL restriction; this adaptation is not an official reproduction. |
| AWS deployment and OpenCV 5 runtime | tested | Public Sydney ECS Express endpoint is live. Remote health and synthetic smoke reported OpenCV 5.0.0 and the deployed build revision. |
| CloudWatch request proof / public HTTPS URL | tested | The smoke request and inspection IDs match structured inspection and request events in CloudWatch; proof is in `results/aws-evidence-20261024t034312z.json`. |
| Remote storage and retention | tested with limits | Images and records use ephemeral task-local storage with one-day cleanup; no inspection S3 writes. Task replacement may delete them sooner. |
| COOL/Graviton | deferred | Not used or claimed. |
| Local submission archive and hash manifest | tested | `dist/reflex-submission.zip` contains the reviewed source, selected synthetic/AWS evidence, both VisA result bundles, and its embedded manifest; the archive SHA-256 and file count are in `dist/reflex-submission-manifest.json`. The packaging check confirms private databases, credentials, runtime caches, and raw VisA images are absent. |
| Public or judge-accessible archive URL, video, and Devpost submission | awaiting human completion | Team/presenter, a ≤5-minute video, external publication/link, and Devpost receipt are not present in the workspace. |

## Current definition of done

The original synthetic vertical slice and its historical AWS benchmark remain separately identified. A pretrained patch-memory improvement has completed the two-class real VisA replay and nine derived robustness families, with lower false-positive rates and higher detection/localization scores. Both real profiles now serve live AWS inference with a real-photo gallery and comparison view; the release passed41local tests and39cloud tests with2standalone integration checks skipped. Six real cloud smoke cases and a public-browser gallery click are verified in `reports/real_demo_20261024/RELEASE.md`. Remaining88/200 real defective images are missed at frozen normal thresholds. A full new-model AWS performance benchmark, useful agentic reinspection, pcb1, independent real data and factory suitability remain unproved. Competition closure still requires presenter/video details, an external archive link and the Devpost receipt.

