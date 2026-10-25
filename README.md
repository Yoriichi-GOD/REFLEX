# REFLEX

REFLEX is an OpenCV 5 visual inspection prototype with original-image, heatmap and overlay evidence. The additive **Safety Station** checks a calibrated colored-parts tabletop assembly and preserves timestamped findings for human review. It provides advisory decisions; it does not control machinery, identify employees, infer fatigue or provide safety certification.

## Start locally

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python backend/scripts/dev.py
```

On Linux or macOS, replace `.venv\Scripts\python` with `.venv/bin/python`. The launcher prints the actual OS-selected loopback addresses for the Inspection Studio, Safety Station and same-origin API. It generates owned software-test clips when absent and does not stop other projects.

Open the printed Safety Station URL, select a generated fixture, confirm permission and calibration, then process it. Generated samples are labeled **SYNTHETIC SOFTWARE TEST**. The original studio remains at `/`; Safety Station is at `/safety`.

Optional real-photograph inspection uses the unchanged frozen v1 candle/cashew profiles and six attributed VisA JPEGs:

```text
.venv\Scripts\python backend/scripts/prepare_public_weights.py
.venv\Scripts\python backend/scripts/dev.py --real
```

The explicit download helper retrieves about 103 MB of public ONNX weights and verifies the pinned SHA-256. Raw dataset archives are excluded. VisA photographs and derived profiles retain CC BY 4.0 attribution; see [third-party notices](THIRD_PARTY_NOTICES.md). The existing live AWS demo remains v1. This extension has not deployed Safety Station to AWS.

## Measured evidence

| Evaluation | Completed work | Outcome and limit |
|---|---|---|
| Real image anomalies | 88 method/group rows over 860 distinct VisA cases | Replay improves, but new-category final AUROC falls and false alerts and cost increase. The primary v2 candidate remains local. Historical custom AU-PRO values are invalid; a correction is included. |
| Procedural software tests | 18 generated held-out clips Ã— 3 policies = 54 actual runs | All three policies tie at 15/18 exact final statuses, zero false clears in this generated set and 5/7 timely supported error clips. Two of four normal clips incorrectly remain HOLD. **No observed agent accuracy gain.** |
| Real procedural or external logical data | **NOT_RUN** | No physical fixture videos were available. Assembly101 video access requires approval; mistake-specific timestamp units remain unverified. Parsing annotations is not video evaluation. |

Read the [anomaly study](benchmarks/anomaly_v2/README.md), [procedural findings](benchmarks/procedural_safety/public/FINDINGS.md), [full CSV](benchmarks/procedural_safety/public/results.csv) and [all 54 procedural cases](benchmarks/procedural_safety/public/index.html). Generated videos are software tests, not real or physically staged assembly benchmarks.

Safety Station displays actual API observations, events and evidence. Human review is appended separately from the machine finding. Video event time and processing duration are distinct. A new-view request waits for actual input; a still image cannot establish a temporal procedure. A calibrated frame is the result of a perspective transform, not the untouched original.

## Checks and reproduction

```text
.venv\Scripts\python -m pytest backend/tests/test_safety.py backend/tests/test_safety_benchmark.py backend/tests/test_core.py backend/tests/test_api.py backend/tests/test_frontend_assets.py -q
node --check frontend/safety.js
node --test ui/extension_20261025/test_safety_core.cjs ui/extension_20261025/test_safety_lifecycle.cjs
.venv\Scripts\python ui/extension_20261025/test_safety_markup.py
.venv\Scripts\python backend/scripts/benchmark_safety.py --output reports/my-new-software-run
```

The benchmark requires an empty output folder, retains all policies and failures, opens test labels after inference and labels its results **SYNTHETIC SOFTWARE TEST**. It does not overwrite published results. Full host regression also uses retained external datasets and ONNX weights; the commands above identify the source-clone core checks. Existing receipts do not establish compatibility on every fresh machine.

Browser rendering, Playwright and physical-camera verification were **NOT_RUN** because available browser control was disabled. API and software checks do not prove responsive layout or browser codec support. An AVI unsupported by the browser can still be decoded by OpenCV and reviewed through JPEG timeline evidence.

For authorized physical clips, align the board quadrilateral and component classes, record the empty-start context, keep annotations separate from inference and lock a new validation/test protocol. Do not retune against the published synthetic test. See [inventory](docs/extension_inventory.md), [architecture](docs/system_architecture.md), [limitations](docs/limitations_and_safety.md), [current status](STATUS.md) and the [original evaluation guide](docs/IMPROVEMENT_V2_GUIDE.md).

## Licensing and submission status

MIT covers REFLEX source code. Data, models, fonts and artwork retain separate terms in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Public source excludes credentials, private uploads and databases, raw dataset archives, feature caches, unlicensed user-fixture bytes, gated or noncommercial annotation assets and private cloud-bundle configuration.

No competition submission or judge video is claimed. Team details, video and submission receipts remain human work.

## Review materials

The [ten-slide YMCA Theme 04 deck](submission/ymca_20261025/REFLEX_YMCA_Theme04_10_Slides.pptx) and [OpenCV paper/slides](submission/opencv_current) are editable review artifacts. Team details, the actual demonstration recording and competition submission receipt remain pending.

## Technical intelligence audit

The [85-question public intelligence report](docs/REFLEX_YMCA_PPT_INTELLIGENCE_PUBLIC.md) audits the implemented architecture, datasets, benchmarks, live AWS boundary and presentation claims. The [numeric ledger and licensed examples](benchmarks/intelligence_20261025) preserve measured results and their limitations. Fresh audit checks passed 138 Python tests, 14 frontend tests, 5 markup tests and 20 separate API assertions; these counts do not establish scientific accuracy or rendered-browser verification.
