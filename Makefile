PYTHON ?= python
API_BASE ?=
DATASET_ID ?= MVTec-AD-v1

.PHONY: install setup demo-data fit-demo up test lint smoke provenance fit-mvtec fit-visa evaluate deploy-aws smoke-aws bench-audit bench-synthetic bench-visa bench-robustness bench-aws-synthetic

install:
	$(PYTHON) -m pip install -r backend/requirements.txt

setup: demo-data fit-demo

demo-data:
	$(PYTHON) backend/scripts/make_fixtures.py

fit-demo:
	$(PYTHON) backend/scripts/fit_demo.py

up:
	$(PYTHON) backend/scripts/dev.py

test:
	$(PYTHON) -m pytest -q backend/tests

lint:
	$(PYTHON) -m compileall -q backend
	node --check frontend/app.js

smoke:
	$(PYTHON) backend/scripts/smoke.py --api-base "$(API_BASE)"

provenance:
	$(PYTHON) backend/scripts/provenance.py

fit-mvtec:
	$(PYTHON) backend/scripts/fit_dataset.py --dataset-dir "$(DATASET_DIR)" --class-name "$(CLASS)" --dataset-id "MVTec-AD-v1"

fit-visa:
	$(PYTHON) backend/scripts/fit_dataset.py --dataset-dir "$(DATASET_DIR)" --class-name "$(CLASS)" --dataset-id "VisA-1cls"

ifeq ($(strip $(DATASET_DIR)),)
evaluate:
	$(PYTHON) backend/scripts/evaluate.py
else
evaluate:
	$(PYTHON) backend/scripts/evaluate_dataset.py --dataset-dir "$(DATASET_DIR)" --class-name "$(CLASS)" --dataset-id "$(DATASET_ID)"
endif

deploy-aws:
	powershell -NoProfile -ExecutionPolicy Bypass -File .\infra\aws\deploy.ps1

smoke-aws:
	$(PYTHON) backend/scripts/smoke.py --api-base "$(API_BASE)" --expect-aws

bench-audit:
	PYTHONPATH=backend $(PYTHON) -m reflex_bench.audit

bench-synthetic:
	PYTHONPATH=backend $(PYTHON) -m reflex_bench.synthetic_smoke

bench-visa:
	PYTHONPATH=backend $(PYTHON) -m reflex_bench.evaluate candle cashew pcb1

bench-robustness:
	PYTHONPATH=backend $(PYTHON) -m reflex_bench.robustness

# Sequential synthetic-only AWS profile: 10 warm-ups + 100 measured uploads
# paced under the service's 10 uploads / 600 seconds guard (about 113 minutes).
bench-aws-synthetic:
	PYTHONPATH=backend $(PYTHON) -m reflex_bench.aws_profile

.PHONY: dev safety-benchmark
dev:
	$(PYTHON) backend/scripts/dev.py
safety-benchmark:
	$(PYTHON) backend/scripts/benchmark_safety.py --output "$(OUT)"
