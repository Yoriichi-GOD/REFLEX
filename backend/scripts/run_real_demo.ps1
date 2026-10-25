param([int]$Port = 8002)
$reflexRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$env:PYTHONPATH = Join-Path $reflexRoot 'backend'
$env:MODEL_DIR = Join-Path $reflexRoot 'data\model'
$env:REFLEX_DATA_DIR = Join-Path $reflexRoot 'data\runtime-real-demo'
$env:REFLEX_PROFILES_DIR = Join-Path $reflexRoot 'demo\profiles'
$env:REFLEX_DEFAULT_PROFILE = 'candle'
$env:REFLEX_EVALUATION_DIR = Join-Path $reflexRoot 'demo\evaluations'
$env:REFLEX_ONNX_WEIGHTS = Join-Path $reflexRoot 'demo\pretrained\resnet50-v1-12.onnx'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& (Join-Path $reflexRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
