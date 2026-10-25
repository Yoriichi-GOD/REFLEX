# Verified local patch-memory profile

Use the `reflex` folder inside Codex scratch as the working copy.

The patch-memory model is fitted for **candle** and **cashew**. Both real profiles now run on AWS alongside the explicitly labeled original synthetic profile; see the [real-image demo guide](REAL_IMAGE_DEMO.md). The new model runs through OpenCV5 DNN, with fixed pretrained ResNet50 features, a projected normal-patch coreset, exact L2 nearest-neighbor comparison, calibrated maps and quality checks. It is an adaptation inspired by PatchCore, not the official WideResNet implementation.

## Open locally

From this folder in PowerShell:

```powershell
.\backend\scripts\run_patch_profile.ps1 -Category candle -Port 8001
```

Open `http://127.0.0.1:8001`. Upload a candle image. To use cashews, stop this local server and launch it with `-Category cashew`. Category mismatches are rejected. Real benchmark profiles do not use the synthetic demo-image buttons. Images remain in local development storage. Scores are anomaly distances, not defect probabilities.

The application uses the same saved memory and thresholds as the benchmark. Its traces explicitly identify the category and do not claim a crop confirmation for this model. The evaluation panel loads only a matching model-hash report. The public AWS endpoint now serves these real profiles. Six live real-image smoke checks are recorded in the [release evidence](../reports/real_demo_20261024/RELEASE.md). Earlier synthetic latency results do not apply to this model; the smoke checks are not a performance benchmark.

## Reproduce from the saved source

Keep raw VisA images outside the repository. The existing dataset location is the sibling `reflex-data/visa/prepared`. Preserve the official one-class split. Exact fit/calibration/development membership and SHA256 hashes are in `reports/improvement_20261024/{category}/membership.json`.

Install the application dependencies and `backend/requirements-benchmark.txt` into a virtual environment, then set `PYTHONPATH=backend`, `OPENBLAS_NUM_THREADS=4` and `OMP_NUM_THREADS=4` **before Python starts**. Acquire the pinned pretrained artifact and export its unchanged feature graph:

```powershell
$env:PYTHONPATH='backend'
$env:OPENBLAS_NUM_THREADS='4'
$env:OMP_NUM_THREADS='4'
.\.venv\Scripts\python.exe -m scripts.get_pretrained '..\reflex-data\models\resnet50-v1-12.onnx'
.\.venv\Scripts\python.exe -m scripts.export_feature_graph '..\reflex-data\models\resnet50-v1-12.onnx'
```

The parent model must match SHA256`3f03fdef724b22947eed826f1eef1dc5c34151bb4c37d634f1db89dfa2dd1526`; the exported graph must match SHA256`13f53653570d3ad98231c463d4ee4ec202306ba3614166f52f10d31e472cb5e6`. Export verifies that all retained parameter tensors and computation nodes are byte-for-byte unchanged. ONNX1.23.2 is the pinned graph preparation version; the runtime does not import ONNX.

The completed run is preserved in `reports/improvement_20261024`. **Copy the project to a separate experiment directory before rerunning**, since the runner's output path is fixed and fitting/evaluation writes into it. Do not overwrite the completed evidence. In that experiment copy:

```powershell
.\.venv\Scripts\python.exe -m reflex_bench.improve train --category candle
.\.venv\Scripts\python.exe -m reflex_bench.improve train --category cashew
.\.venv\Scripts\python.exe -m reflex_bench.improve freeze
.\.venv\Scripts\python.exe -m reflex_bench.improve evaluate --category candle --robust
.\.venv\Scripts\python.exe -m reflex_bench.improve evaluate --category cashew --robust
.\.venv\Scripts\python.exe -m reflex_bench.improvement_report
```

Override `REFLEX_VISA_PREPARED` and `REFLEX_ONNX_WEIGHTS` if external data is stored elsewhere. The normal memory never uses test defects, masks, or normal calibration/development images. The original official test split has been exposed during development: future generalization claims require independent data.

## Verification and remaining gaps

The tests cover true pretrained inference and saved-model reload, weight/bank integrity, train/calibration disjointness, RGB normalization, coordinate mapping, nearest-neighbor distances, deterministic coreset sampling, category rejection, API score agreement, and preserved synthetic behavior. Exact results are in the comparison report and verification record.

Agentic second-look accuracy gain, official PatchCore parity, pcb1, external real datasets, fresh blind validation and a full changed-model AWS performance benchmark remain separate tasks. Do not use this profile to certify industrial safety or automatically accept physical parts based on these limited benchmarks.
