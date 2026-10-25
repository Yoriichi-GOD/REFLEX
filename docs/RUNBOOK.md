# Runbook

## Start locally

1. Install the pinned requirements from `backend/requirements.txt`.
2. Run `python backend/scripts/setup.py` to regenerate the seeded demo assets and fit the normal-only profile.
3. Start with `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`.
4. Confirm `/api/health` reports OpenCV `5.x`, model mode `opencv_normal_bank`, and `model_ready: true`.
5. Run the UI normal, scratch, and blurred cases. Then run `python -m pytest -q backend/tests` and `python backend/scripts/smoke.py`.

## Failure handling

- **OpenCV version is not 5:** install the pinned requirements in the active environment; service startup intentionally fails instead of falling back to OpenCV 4.
- **Normal bank missing or hash mismatch:** run `python backend/scripts/fit_demo.py`. The service checks the bank hash before inference.
- **Corrupt/oversized image:** use PNG/JPEG/WebP under the configured compressed size, dimensions, and pixel count. A retake request includes focus/exposure flags.
- **Agent crop does not corroborate:** leave the model result at `NEEDS_REVIEW`; do not force a pass.
- **Review request fails:** inspect the `inspection_id`; if `REFLEX_REVIEW_TOKEN` is configured, send it in `X-Review-Token`. Review records do not modify the model decision.
- **Inspection history disappears:** local data resides in `data/inspections.sqlite3` and `data/assets/`; it is removed after the configured retention window. Do not delete the data folder while the service is running.
- **Benchmark model not found:** `fit_dataset.py` writes MVTec profiles to `data/models/mvtec_<class>` and VisA profiles to `data/models/visa_<class>` by default. Set `MODEL_DIR` to that path before starting the API to activate a class-specific profile locally. The deployed AWS service still uses the synthetic profile.
- **AWS action requested:** see [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md). The current project deliberately does not write inspection data to S3.

## Health and evidence

- `/api/health`: actual OpenCV version, model readiness, build revision, runtime indicator.
- `/api/ready`: 503 if the OpenCV 5 model bank is unavailable.
- `results/eval_*.json`: measured synthetic and selected VisA evaluations; `docs/EVALUATION.md` identifies each scope.
- `results/latency_*.csv`: per-case latency, decisions, tool names.
- `results/provenance_<run-id>.json`: timestamped file hashes and runtime manifest; each run gets a new file so older evidence is preserved.
