param(
    [ValidateSet('candle', 'cashew')][string]$Category = 'candle',
    [int]$Port = 8001
)
$reflexRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$env:MODEL_DIR = Join-Path $reflexRoot "reports\improvement_20261024\models\$Category"
$env:REFLEX_ONNX_WEIGHTS = Join-Path (Split-Path $reflexRoot -Parent) 'reflex-data\models\resnet50-v1-12.onnx'
$env:REFLEX_DATA_DIR = Join-Path $reflexRoot "data\runtime-patch-$Category"
$env:OPENBLAS_NUM_THREADS = '4'
$env:OMP_NUM_THREADS = '4'
$env:PYTHONPATH = Join-Path $reflexRoot 'backend'
& (Join-Path $reflexRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
