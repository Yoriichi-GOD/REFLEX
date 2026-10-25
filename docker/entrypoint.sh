#!/bin/sh
set -eu
if [ -f /app/demo/profiles/candle/patch_bank.npz ]; then
  export REFLEX_PROFILES_DIR=/app/demo/profiles
  export REFLEX_DEFAULT_PROFILE=candle
  export REFLEX_EVALUATION_DIR=/app/demo/evaluations
  export REFLEX_ONNX_WEIGHTS=/app/demo/pretrained/resnet50-v1-12.onnx
  export OPENBLAS_NUM_THREADS=1
  export OMP_NUM_THREADS=1
fi
if [ ! -d /app/data/synthetic/train_normal ]; then
  python /app/backend/scripts/make_fixtures.py
fi
if [ ! -f /app/data/model/normal_bank.npz ]; then
  python /app/backend/scripts/fit_demo.py
fi
exec python -m uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=10.240.0.0/16
