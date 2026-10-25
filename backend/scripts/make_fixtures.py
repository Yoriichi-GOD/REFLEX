from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

DATA = ROOT / "data" / "synthetic"
SAMPLES = ROOT / "demo" / "samples"
WIDTH, HEIGHT = 480, 360


def _rounded_mask(shape: tuple[int, int], box: tuple[int, int, int, int], radius: int) -> np.ndarray:
    h, w = shape
    x1, y1, x2, y2 = box
    mask = np.zeros((h, w), np.uint8)
    cv2.rectangle(mask, (x1 + radius, y1), (x2 - radius, y2), 255, -1)
    cv2.rectangle(mask, (x1, y1 + radius), (x2, y2 - radius), 255, -1)
    for x, y in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius), (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
        cv2.circle(mask, (x, y), radius, 255, -1, cv2.LINE_AA)
    return mask


def make_normal(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    image = np.full((HEIGHT, WIDTH, 3), 25, np.uint8)
    # A fictional machined plate with repeatable geometry and varied normal surface texture.
    cv2.rectangle(image, (57, 35), (423, 325), (64, 72, 77), -1, cv2.LINE_AA)
    cv2.rectangle(image, (64, 41), (416, 318), (109, 119, 123), -1, cv2.LINE_AA)
    plate = _rounded_mask((HEIGHT, WIDTH), (70, 48, 410, 311), 12)
    cv2.fillPoly(image, [np.array([[75, 48], [405, 48], [410, 55], [70, 55]], np.int32)], (143, 151, 153))
    cv2.rectangle(image, (73, 57), (407, 303), (135, 143, 146), -1)
    cv2.rectangle(image, (73, 57), (407, 303), (160, 167, 168), 1)
    # Mild brushed-metal lines and fixed seams form the learned normal reference.
    for _ in range(38):
        y = int(rng.integers(62, 299))
        x1 = int(rng.integers(75, 175))
        x2 = int(rng.integers(280, 406))
        value = int(rng.integers(129, 143))
        cv2.line(image, (x1, y), (x2, y), (value, value + 2, value + 3), 1, cv2.LINE_AA)
    for x in (87, 393):
        cv2.line(image, (x, 66), (x, 295), (114, 122, 126), 1, cv2.LINE_AA)
    cv2.line(image, (100, 279), (380, 279), (118, 126, 130), 2, cv2.LINE_AA)
    cv2.line(image, (100, 81), (380, 81), (166, 172, 173), 1, cv2.LINE_AA)
    for x, y in ((78, 54), (402, 54), (78, 304), (402, 304)):
        cv2.circle(image, (x, y), 10, (67, 73, 76), -1, cv2.LINE_AA)
        cv2.circle(image, (x, y), 7, (185, 191, 191), -1, cv2.LINE_AA)
        cv2.circle(image, (x, y), 3, (91, 98, 101), -1, cv2.LINE_AA)
        cv2.line(image, (x - 4, y), (x + 4, y), (211, 215, 214), 1, cv2.LINE_AA)
    # Subtle per-capture illumination and sensor noise vary without adding labeled defects.
    brightness = float(rng.uniform(-1.6, 1.6))
    image = np.clip(image.astype(np.float32) + brightness, 0, 255)
    noise = rng.normal(0, 1.05, image.shape).astype(np.float32)
    image = np.clip(image + noise, 0, 255).astype(np.uint8)
    return image


def add_defect(image: np.ndarray, kind: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    result = image.copy()
    mask = np.zeros(image.shape[:2], np.uint8)
    if kind == "scratch":
        points = np.array([[173, 143], [203, 149], [238, 145], [279, 157], [314, 151]], np.int32)
        cv2.polylines(result, [points], False, (53, 60, 62), 4, cv2.LINE_AA)
        highlight = points.copy()
        highlight[:, 1] -= 3
        cv2.polylines(result, [highlight], False, (211, 218, 217), 1, cv2.LINE_AA)
        cv2.polylines(mask, [points], False, 255, 8, cv2.LINE_AA)
    elif kind == "pit":
        x, y = int(rng.integers(170, 300)), int(rng.integers(135, 225))
        cv2.circle(result, (x, y), 9, (75, 82, 84), -1, cv2.LINE_AA)
        cv2.circle(result, (x - 2, y - 2), 4, (45, 52, 54), -1, cv2.LINE_AA)
        cv2.circle(mask, (x, y), 11, 255, -1, cv2.LINE_AA)
    elif kind == "edge_chip":
        points = np.array([[70, 195], [82, 184], [84, 211], [70, 220]], np.int32)
        cv2.fillPoly(result, [points], (33, 40, 42), cv2.LINE_AA)
        cv2.fillPoly(mask, [points], 255, cv2.LINE_AA)
    elif kind == "discoloration":
        x, y = int(rng.integers(170, 300)), int(rng.integers(130, 225))
        overlay = result.copy()
        cv2.ellipse(overlay, (x, y), (20, 12), int(rng.integers(-20, 20)), 0, 360, (89, 127, 106), -1, cv2.LINE_AA)
        result = cv2.addWeighted(result, 0.52, overlay, 0.48, 0)
        cv2.ellipse(mask, (x, y), (22, 14), 0, 0, 360, 255, -1, cv2.LINE_AA)
    elif kind == "missing_component":
        x, y = 78, 54
        cv2.circle(result, (x, y), 10, (130, 138, 141), -1, cv2.LINE_AA)
        cv2.circle(result, (x, y), 7, (142, 149, 151), -1, cv2.LINE_AA)
        cv2.circle(mask, (x, y), 11, 255, -1, cv2.LINE_AA)
    else:
        raise ValueError(f"Unknown synthetic defect: {kind}")
    return result, mask


def save(path: Path, image: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Failed to write {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    for folder in (DATA / "train_normal", DATA / "calibration_normal", DATA / "eval" / "normal", DATA / "eval" / "defect", DATA / "eval" / "masks"):
        folder.mkdir(parents=True, exist_ok=True)
    records = []
    def record(path: Path, category: str, intended: str, mask_path: Path | None = None):
        records.append({
            "asset_id": path.stem, "ownership": "seeded synthetic fixture generated by REFLEX",
            "license": "CC0-1.0 code-generated pixel data", "source_url": None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "camera_conditions": "not applicable; synthetic",
            "class": "synthetic_machined_plate", "label_source": "generator parameters; evaluation only" if category == "eval" else "normal by construction",
            "synthetic": True, "ground_truth_mask": str(mask_path.relative_to(ROOT)).replace("\\", "/") if mask_path else None,
            "intended_use": intended, "redistributed": True,
        })
    def record_mask(path: Path, intended: str):
        records.append({
            "asset_id": path.stem, "ownership": "seeded synthetic ground-truth mask generated by REFLEX",
            "license": "CC0-1.0 code-generated pixel data", "source_url": None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "camera_conditions": "not applicable; synthetic",
            "class": "synthetic_machined_plate", "label_source": "exact synthetic generator mask",
            "synthetic": True, "ground_truth_mask": str(path.relative_to(ROOT)).replace("\\", "/"),
            "intended_use": intended, "redistributed": True,
        })
    for i in range(40):
        p = DATA / "train_normal" / f"normal_{i:03d}.png"
        save(p, make_normal(10_000 + i)); record(p, "train", "train")
    for i in range(12):
        p = DATA / "calibration_normal" / f"normal_{i:03d}.png"
        save(p, make_normal(20_000 + i)); record(p, "calibration", "calibration")
    for i in range(12):
        p = DATA / "eval" / "normal" / f"normal_{i:03d}.png"
        save(p, make_normal(30_000 + i)); record(p, "eval", "eval")
    defects = []
    for kind in ("scratch", "pit", "edge_chip", "discoloration", "missing_component"):
        for i in range(4):
            image, mask = add_defect(make_normal(40_000 + len(defects)), kind, 50_000 + len(defects))
            stem = f"{kind}_{i:02d}"
            p = DATA / "eval" / "defect" / f"{stem}.png"
            mp = DATA / "eval" / "masks" / f"{stem}.png"
            save(p, image); save(mp, mask); record(p, "eval", "eval", mp); record_mask(mp, "eval")
            defects.append({"image": str(p.relative_to(ROOT)).replace("\\", "/"), "mask": str(mp.relative_to(ROOT)).replace("\\", "/"), "defect_type": kind, "label": 1})
    normal_demo = make_normal(60_001)
    scratch_demo, scratch_mask = add_defect(make_normal(60_002), "scratch", 60_099)
    blur_demo = cv2.GaussianBlur(make_normal(60_003), (0, 0), 8.0)
    sample_records = []
    for name, image, mask in (("normal", normal_demo, None), ("scratch", scratch_demo, scratch_mask), ("blurred", blur_demo, None)):
        image_path = SAMPLES / f"{name}.png"
        digest = save(image_path, image)
        mask_path = None
        if mask is not None:
            mask_path = SAMPLES / "scratch_mask.png"
            save(mask_path, mask)
        sample_records.append({
            "id": name, "title": {"normal": "Reference-like plate", "scratch": "Faint surface change", "blurred": "Soft-focus capture"}[name],
            "description": {"normal": "Seeded synthetic normal surface", "scratch": "Seeded synthetic scratch; mask retained for evaluation only", "blurred": "Seeded synthetic low-focus image"}[name],
            "image_url": f"/demo/samples/{name}.png", "sha256": digest, "synthetic": True,
            "mask_path": str(mask_path.relative_to(ROOT)).replace("\\", "/") if mask_path else None,
        })
        records.append({
            "asset_id": f"demo_{name}", "ownership": "seeded synthetic fixture generated by REFLEX",
            "license": "CC0-1.0 code-generated pixel data", "source_url": None, "sha256": digest,
            "camera_conditions": "not applicable; synthetic", "class": "synthetic_machined_plate",
            "label_source": "scenario description for demo selection; inference does not read scenario labels",
            "synthetic": True, "ground_truth_mask": str((SAMPLES / "scratch_mask.png").relative_to(ROOT)).replace("\\", "/") if name == "scratch" else None,
            "intended_use": "demo", "redistributed": True,
        })
        if name == "scratch" and mask_path is not None:
            record_mask(mask_path, "demo")
    labels = {
        "dataset": "REFLEX seeded synthetic fixture set",
        "seed_policy": "disjoint integer seed ranges per training, calibration, evaluation and demo groups",
        "train_normal": [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((DATA / "train_normal").glob("*.png"))],
        "calibration_normal": [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((DATA / "calibration_normal").glob("*.png"))],
        "eval_normal": [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((DATA / "eval" / "normal").glob("*.png"))],
        "eval_defect": defects,
        "records": records,
    }
    (DATA / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    (ROOT / "demo" / "cases.json").write_text(json.dumps(sample_records, indent=2), encoding="utf-8")
    (ROOT / "data" / "assets_manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Generated {len(labels['train_normal'])} train normals, {len(labels['calibration_normal'])} calibration normals, {len(labels['eval_normal'])} eval normals, {len(defects)} synthetic eval defects, and {len(sample_records)} demo cases.")
    print("All pixels and labels are synthetic; no real-world or MVTec metrics are implied.")
    return labels


if __name__ == "__main__":
    build()
