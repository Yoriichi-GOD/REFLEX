# Setup and verification

[README](../README.md) · [Reviewer tour](REVIEWER_GUIDE.md) · [Architecture](ARCHITECTURE_GUIDE.md) · [Status](PROJECT_STATUS.md)

## Requirements and scope

Use Python 3.12 or newer, Git, and an environment that can install the [pinned Python dependencies](../backend/requirements.txt). The recorded local environment used Python 3.14.6; the measured cloud image used 3.12.15. These are observed environments, not a tested platform matrix. OpenCV major version **5** is enforced at service startup. Node.js is needed for the JavaScript checks below, not to serve the interface.

No AWS credentials are needed to run the local application. Do not run deployment scripts simply to preview it.

## Real product photographs

From the repository root on Windows PowerShell:

```powershell
git clone https://github.com/Yoriichi-GOD/REFLEX.git
cd REFLEX
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python backend/scripts/prepare_public_weights.py
.venv\Scripts\python backend/scripts/dev.py --real
```

On Linux/macOS:

```sh
git clone https://github.com/Yoriichi-GOD/REFLEX.git
cd REFLEX
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/scripts/prepare_public_weights.py
.venv/bin/python backend/scripts/dev.py --real
```

If you already have this checkout, start with the environment step; do not clone a nested repository.

The helper explicitly downloads approximately 103 MB of public ResNet-50 ONNX weights, checks the pinned SHA-256 and refuses an altered existing file. It does not acquire raw industrial datasets. Review the [model and data terms](../THIRD_PARTY_NOTICES.md).

The launcher holds an OS-selected free loopback port and prints the actual Inspection Studio, Safety Station and API URLs. Open the printed Studio URL, select **VisA · candle** or **VisA · cashew**, then choose a real example. It runs the retained **v1** real-image profiles. `--real` does not activate v2 or reproduce the full image study.

Stop the server with Ctrl+C in its own terminal. It does not stop unrelated projects.

## Generated samples without model weights

After installing dependencies, omit the weights helper and `--real`:

```powershell
.venv\Scripts\python backend/scripts/dev.py
```

Use `.venv/bin/python` on Linux/macOS. This prepares generated fixtures when absent and serves the original studio plus the additive `/safety` page. It does not substitute synthetic media for real industrial evaluation.

Safety Station needs a selected fixture or authorized input, consent and manual board calibration. Its supported visual vocabulary is a colored-parts teaching panel. Generated fixtures remain labeled **SYNTHETIC SOFTWARE TEST**. A still cannot establish an entire temporal procedure. Physical-camera and real procedure validation remain open.

## Verify the software

The following source-clone checks are the same bounded suite used by [the repository workflow](../.github/workflows/source-checks.yml). On Windows:

```powershell
.venv\Scripts\python -m pytest backend/tests/test_safety.py backend/tests/test_safety_benchmark.py backend/tests/test_core.py backend/tests/test_api.py backend/tests/test_frontend_assets.py -q
node --test ui/extension_20261025/test_safety_core.cjs ui/extension_20261025/test_safety_lifecycle.cjs
.venv\Scripts\python ui/extension_20261025/test_safety_markup.py
```

Use `.venv/bin/python` on Linux/macOS. Optional syntax check: `node --check frontend/safety.js`.

These tests establish their tested software behavior. They do not establish model accuracy, actual camera operation, a responsive-browser acceptance matrix or fresh-machine compatibility. Existing [public check receipts](verification/PUBLIC_SOURCE_VERIFICATION.json) identify the recorded run and its scope; they are historical evidence, not tests silently rerun whenever this page is read.

To execute the generated-video software benchmark, choose a **new output directory**:

```powershell
.venv\Scripts\python backend/scripts/benchmark_safety.py --output reports/my-new-software-run
```

This is an opt-in experiment, not required for setup. The evaluator refuses an existing output location, keeps all policy outcomes and identifies generated media. Preserve the [published results](../benchmarks/procedural_safety/public/FINDINGS.md). The real-image study also needs separately acquired licensed data and retained fitted artifacts; see [its reproduction limits](../benchmarks/anomaly_v2/README.md#reproduction-scope) before attempting a full rerun. Do not run older hardcoded-output evaluators against the frozen study.

## Common setup problems

| Symptom | Check |
| --- | --- |
| Startup rejects OpenCV 4 | Use the intended virtual environment and install the pinned requirements; do not disable the version gate. |
| Existing environment reports `No module named pip` | With a Python distribution that includes `ensurepip`, bootstrap that environment using `.venv\Scripts\python -m ensurepip --upgrade`, then install the pinned requirements. This recovery command was checked for availability, not executed during the documentation task. |
| `--real` reports missing weights | Run `prepare_public_weights.py`; use `--check-only` to verify an existing download without fetching it. |
| Existing weights hash mismatch | Preserve the file and inspect its provenance; the helper intentionally refuses to replace it silently. |
| A partially downloaded `.download` file remains | Inspect the failed download before retrying; do not overwrite a complete pinned artifact. |
| Port 8000 is occupied | Use `dev.py` without a fixed port and open the address it prints. |
| Browser will not play an AVI | Codec support differs. The OpenCV replay path and saved JPEG evidence are distinct from native browser playback. |
| Public demo returns a rate-limit message | Pause before retrying; its guard is not a production capacity measurement. |

The Docker/Compose and infrastructure files are retained implementation material, not the recommended local extension launcher. They do not prove a fresh Docker Desktop run or permission to deploy the local candidates. For the actual cloud boundary, use [the architecture guide](ARCHITECTURE_GUIDE.md#aws-v1) and [AWS evidence](aws_evidence.md).
