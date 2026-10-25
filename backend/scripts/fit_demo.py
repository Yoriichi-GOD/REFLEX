from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.model import fit_normal_bank

data = ROOT / "data" / "synthetic"
train = sorted((data / "train_normal").glob("*.png"))
calibration = sorted((data / "calibration_normal").glob("*.png"))
metadata = fit_normal_bank(train, calibration, ROOT / "data" / "model", seed=20261023, source="synthetic")
print(f"Fitted {metadata['model_mode']} from {metadata['training_count']} normal-only images; calibrated using {metadata['calibration_count']} disjoint normal images.")
print(f"Image threshold={metadata['image_threshold']:.6f}; pixel threshold={metadata['pixel_threshold']:.6f}; bank SHA256={metadata['normal_bank_sha256']}")
