"""Run the exact packaged source in an isolated directory before cloud build."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser=argparse.ArgumentParser();parser.add_argument("archive",type=Path);parser.add_argument("--log",type=Path,required=True)
    args=parser.parse_args()
    stage=Path(tempfile.mkdtemp(prefix="reflex-bundle-check-")).resolve()
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            if not (stage/name).resolve().is_relative_to(stage):raise ValueError("Unsafe archive path")
        archive.extractall(stage)
    environment=dict(os.environ)
    for key in ("REFLEX_ONNX_WEIGHTS","REFLEX_VISA_PREPARED","REFLEX_PROFILES_DIR","REFLEX_DEFAULT_PROFILE","REFLEX_EVALUATION_DIR"):
        environment.pop(key,None)
    environment.update(PYTHONPATH=str(stage/"backend"),REFLEX_DATA_DIR=str(stage/"data"),MODEL_DIR=str(stage/"data"/"model"),PYTHONDONTWRITEBYTECODE="1",OPENBLAS_NUM_THREADS="4",OMP_NUM_THREADS="4")
    result=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider",str(stage/"backend"/"tests")],cwd=stage,env=environment,capture_output=True,text=True)
    args.log.parent.mkdir(parents=True,exist_ok=True)
    args.log.write_text(result.stdout+result.stderr,encoding="utf-8")
    print(json.dumps({"bundle_test_exit_code":result.returncode,"isolated_imports":True,"last_lines":result.stdout.splitlines()[-2:]}))
    raise SystemExit(result.returncode)


if __name__=="__main__":main()
