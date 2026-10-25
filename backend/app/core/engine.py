"""Select the explicitly configured model profile, preserving legacy support."""
from __future__ import annotations
from functools import lru_cache
import json
import os
from pathlib import Path
import cv2

from app.config import MODEL_DIR
from app.core import model as legacy
from app.core.patch_memory import PatchMemory
from app.core.patch_memory_v2 import PatchMemoryV2, VERSION as V2_VERSION


@lru_cache(maxsize=2)
def _patch_profile(directory: str, signature: tuple, weights: str) -> PatchMemory:
    cv2.setNumThreads(4)
    meta=json.loads((Path(directory)/"metadata.json").read_text(encoding="utf-8"))
    cls=PatchMemoryV2 if meta.get("model_version")==V2_VERSION else PatchMemory
    return cls.load(Path(directory),Path(weights))


def load_bank(model_dir: Path = MODEL_DIR):
    directory=Path(model_dir)
    metadata=json.loads((directory/"metadata.json").read_text(encoding="utf-8"))
    if metadata.get("model_mode")!="opencv_dnn_patch_memory":
        return legacy.load_bank(directory)
    weights_text=os.getenv("REFLEX_ONNX_WEIGHTS")
    if not weights_text:
        raise RuntimeError("REFLEX_ONNX_WEIGHTS must identify verified pretrained weights for this profile")
    weights=Path(weights_text).resolve()
    files=[directory/"metadata.json",directory/"patch_bank.npz",weights,weights.with_suffix(".features.onnx")]
    if metadata.get("detail_directory"):
        detail=(directory/metadata["detail_directory"]).resolve()
        if not detail.is_relative_to(directory.resolve()):
            raise RuntimeError("Detail profile must remain inside parent directory")
        files.extend([detail/"metadata.json",detail/"patch_bank.npz"])
    signature=tuple((p.stat().st_mtime_ns,p.stat().st_size) for p in files)
    model=_patch_profile(str(directory.resolve()),signature,str(weights))
    return model,None,model.metadata


def analyze(image,mean=None,scale=None,metadata=None):
    if mean is None or metadata is None:
        mean,scale,metadata=load_bank()
    if isinstance(mean,PatchMemory):
        result=mean.analyze(image)
        result["score_type"]="local_normal_patch_support_l2" if isinstance(mean,PatchMemoryV2) else "nearest_normal_patch_l2"
        return result
    result=legacy.analyze(image,mean,scale,metadata)
    result["category"]=metadata.get("category","synthetic_machined_plate")
    return result
