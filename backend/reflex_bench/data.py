"""Dataset readers and deterministic evaluation-grid transforms."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import random

import cv2
import numpy as np

from app.core.model import read_bgr


@dataclass(frozen=True)
class Case:
    case_id: str
    image_path: Path
    mask_path: Path | None
    label: int
    source: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def list_images(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"})


def split_normal(paths: list[Path], seed: int = 20261023, calibration_fraction: float = 0.2) -> tuple[list[Path], list[Path]]:
    if len(paths) < 8 or not 0 < calibration_fraction < 1:
        raise ValueError("Need >=8 normal images and a calibration fraction in (0,1)")
    ordered = sorted(paths, key=lambda p: p.as_posix().casefold())
    random.Random(seed).shuffle(ordered)
    n_cal = max(4, round(len(ordered) * calibration_fraction))
    n_cal = min(n_cal, len(ordered) - 4)
    return sorted(ordered[n_cal:]), sorted(ordered[:n_cal])


def visa_cases(category_root: Path) -> tuple[list[Path], list[Path], list[Case]]:
    train = list_images(category_root / "train" / "good")
    if len(train) < 8:
        raise FileNotFoundError(f"Missing/short VisA normal training set: {category_root / 'train' / 'good'}")
    good = [Case(f"good/{p.name}", p, None, 0, "VisA") for p in list_images(category_root / "test" / "good")]
    defect_dir = category_root / "test" / "bad"
    mask_dir = category_root / "ground_truth" / "bad"
    bad: list[Case] = []
    missing = []
    for p in list_images(defect_dir):
        mask = mask_dir / f"{p.stem}_mask.png"
        if not mask.exists():
            missing.append(str(mask))
            continue
        bad.append(Case(f"bad/{p.name}", p, mask, 1, "VisA"))
    if missing:
        raise FileNotFoundError(f"{len(missing)} VisA masks missing; first: {missing[0]}")
    if not good or not bad:
        raise ValueError("VisA test set requires normal and defective images")
    return train, good, bad


def eval_grid(score_map: np.ndarray, mask: np.ndarray | None, max_side: int = 256) -> tuple[np.ndarray, np.ndarray | None]:
    h, w = score_map.shape[:2]
    scale = min(1.0, float(max_side) / max(h, w))
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    score = cv2.resize(score_map.astype(np.float32), size, interpolation=cv2.INTER_LINEAR)
    truth = None
    if mask is not None:
        truth = cv2.resize((mask > 0).astype(np.uint8), size, interpolation=cv2.INTER_NEAREST)
    return score, truth


def read_mask(path: Path | None, image_shape: tuple[int, ...]) -> np.ndarray:
    h, w = image_shape[:2]
    if path is None:
        return np.zeros((h, w), dtype=np.uint8)
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError(f"Could not decode mask {path}")
    if mask.shape != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    return (mask > 0).astype(np.uint8)


def image_case(case: Case) -> tuple[np.ndarray, np.ndarray]:
    image = read_bgr(case.image_path)
    return image, read_mask(case.mask_path, image.shape)
