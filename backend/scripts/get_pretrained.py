"""Acquire the exact public pretrained artifact; fail closed on hash mismatch."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import urllib.request

from app.core.patch_memory import WEIGHTS_SHA256, WEIGHTS_URL, digest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    target=args.destination.resolve()
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or digest(target)!=WEIGHTS_SHA256:
        partial=target.with_suffix(".download")
        urllib.request.urlretrieve(WEIGHTS_URL,partial)
        if digest(partial)!=WEIGHTS_SHA256:
            raise RuntimeError("Downloaded weights do not match official ONNX Git LFS SHA256")
        partial.replace(target)
    manifest={"url":WEIGHTS_URL,"sha256":digest(target),"bytes":target.stat().st_size,
              "license":"Apache-2.0", "source":"https://github.com/onnx/models/tree/main/validated/vision/classification/resnet",
              "upstream_hash_source":"https://raw.githubusercontent.com/onnx/models/main/validated/vision/classification/resnet/model/resnet50-v1-12.onnx"}
    target.with_suffix(".provenance.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest))


if __name__=="__main__":main()
