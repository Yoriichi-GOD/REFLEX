"""Immutable per-request model selection; no global mutable active category."""
from __future__ import annotations
import json
import os
from pathlib import Path

from app.config import MODEL_DIR


def directories(fallback: Path = MODEL_DIR) -> dict[str, Path]:
    result = {}
    root = os.getenv("REFLEX_PROFILES_DIR")
    if root:
        for category in ("candle", "cashew"):
            path = Path(root) / category
            metadata = path / "metadata.json"
            if metadata.exists():
                meta = json.loads(metadata.read_text(encoding="utf-8"))
                if meta.get("category") != category or meta.get("model_mode") != "opencv_dnn_patch_memory":
                    raise RuntimeError("Real-image profile category or mode mismatch")
                result[category] = path
    if (fallback / "metadata.json").exists():
        metadata = json.loads((fallback / "metadata.json").read_text(encoding="utf-8"))
        result[metadata.get("category", "synthetic_machined_plate")] = fallback
    return result


def resolve(category: str | None, fallback: Path = MODEL_DIR) -> Path:
    options = directories(fallback)
    selected = category or os.getenv("REFLEX_DEFAULT_PROFILE") or next(iter(options), None)
    if selected not in options:
        raise ValueError("CATEGORY_UNSUPPORTED")
    return options[selected]
