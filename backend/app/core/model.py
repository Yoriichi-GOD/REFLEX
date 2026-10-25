from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from app.config import MODEL_DIR
from app.core.image_io import sha256_bytes
from app.core.quality import foreground_bbox, inspect_quality

FEATURE_WIDTH = 120
FEATURE_HEIGHT = 90
MODEL_VERSION = "reflex-opencv-normal-bank-1"


def read_bgr(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    return image


def feature_map(image: np.ndarray) -> np.ndarray:
    small = cv2.resize(image, (FEATURE_WIDTH, FEATURE_HEIGHT), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    gray = lab[:, :, 0].astype(np.float32) / 255.0
    local = gray - cv2.GaussianBlur(gray, (9, 9), 0)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    chroma = cv2.magnitude(lab[:, :, 1].astype(np.float32) - 128.0, lab[:, :, 2].astype(np.float32) - 128.0) / 181.0
    return np.stack((gray, local, lap, grad, chroma), axis=2).astype(np.float32)


def _score_features(features: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    z = np.abs((features - mean) / scale)
    score = np.sqrt(np.mean(np.minimum(z, 30.0) ** 2, axis=2))
    return cv2.GaussianBlur(score.astype(np.float32), (3, 3), 0.7)


def _image_score(score_map: np.ndarray) -> float:
    return float(np.quantile(score_map, 0.995))


def fit_normal_bank(
    training_paths: list[Path], calibration_paths: list[Path], output_dir: Path = MODEL_DIR,
    *, seed: int = 20261023, source: str = "synthetic",
) -> dict:
    if len(training_paths) < 4 or len(calibration_paths) < 4:
        raise ValueError("Normal-only fitting needs at least 4 training and 4 calibration images.")
    train = np.stack([feature_map(read_bgr(p)) for p in training_paths])
    # Fit a spatially indexed robust normal reference. No defect examples are passed to this function.
    mean = np.median(train, axis=0).astype(np.float32)
    mad = np.median(np.abs(train - mean), axis=0).astype(np.float32) * 1.4826
    floors = np.asarray([0.018, 0.012, 0.014, 0.018, 0.018], dtype=np.float32)
    scale = np.maximum(mad, floors.reshape(1, 1, -1)).astype(np.float32)
    calibration_maps = np.stack([_score_features(feature_map(read_bgr(p)), mean, scale) for p in calibration_paths])
    calibration_image_scores = np.asarray([_image_score(m) for m in calibration_maps], dtype=np.float32)
    image_threshold = float(np.quantile(calibration_image_scores, 0.95, method="higher"))
    pixel_threshold = float(np.quantile(calibration_maps, 0.995, method="higher"))
    output_dir.mkdir(parents=True, exist_ok=True)
    bank_path = output_dir / "normal_bank.npz"
    np.savez_compressed(bank_path, mean=mean, scale=scale)
    bank_sha = hashlib.sha256(bank_path.read_bytes()).hexdigest()
    metadata = {
        "model_version": MODEL_VERSION,
        "category": source.rsplit(":", 1)[1] if ":" in source else "synthetic_machined_plate",
        "model_mode": "opencv_normal_bank",
        "detector": "OpenCV 5 spatial normal-feature median/MAD bank",
        "feature_channels": ["lab_lightness", "local_lightness_residual", "absolute_laplacian", "sobel_magnitude", "lab_chroma"],
        "feature_grid": [FEATURE_WIDTH, FEATURE_HEIGHT],
        "training_count": len(training_paths),
        "calibration_count": len(calibration_paths),
        "calibration_method": "95th percentile (higher order statistic) of per-image 99.5th-percentile map score, using normal calibration images only",
        "pixel_threshold_method": "99.5th percentile of normal calibration-map pixels; heuristic finite-sample threshold",
        "image_threshold": image_threshold,
        "pixel_threshold": pixel_threshold,
        "calibration_image_scores": [float(v) for v in calibration_image_scores],
        "calibration_seed": int(seed),
        "data_source": source,
        "synthetic": source == "synthetic",
        "training_sha256": [sha256_bytes(p.read_bytes()) for p in training_paths],
        "calibration_sha256": [sha256_bytes(p.read_bytes()) for p in calibration_paths],
        "normal_bank_sha256": bank_sha,
        "feature_normalization": "per-location median and 1.4826*MAD; fixed channel floors [0.018,0.012,0.014,0.018,0.018]",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def load_bank(model_dir: Path = MODEL_DIR) -> tuple[np.ndarray, np.ndarray, dict]:
    npz_path = model_dir / "normal_bank.npz"
    metadata_path = model_dir / "metadata.json"
    if not npz_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("Normal bank is missing. Run `make setup` or `make fit-demo`.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    bank_sha = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    if bank_sha != metadata.get("normal_bank_sha256"):
        raise RuntimeError("Normal bank SHA256 does not match its manifest.")
    with np.load(npz_path) as bank:
        mean = bank["mean"].astype(np.float32)
        scale = bank["scale"].astype(np.float32)
    return mean, scale, metadata


def analyze(image: np.ndarray, mean: np.ndarray | None = None, scale: np.ndarray | None = None, metadata: dict | None = None) -> dict:
    if mean is None or scale is None or metadata is None:
        mean, scale, metadata = load_bank()
    quality = inspect_quality(image)
    features = feature_map(image)
    small_map = _score_features(features, mean, scale)
    height, width = image.shape[:2]
    full_map = cv2.resize(small_map, (width, height), interpolation=cv2.INTER_CUBIC)
    score = _image_score(small_map)
    pixel_threshold = float(metadata["pixel_threshold"])
    regions = extract_regions(small_map, pixel_threshold, (width, height))
    return {
        "score": score,
        "threshold": float(metadata["image_threshold"]),
        "pixel_threshold": pixel_threshold,
        "score_margin": (score - float(metadata["image_threshold"])) / max(float(np.std(metadata["calibration_image_scores"])), 1e-6),
        "quality": quality,
        "foreground_bbox_xyxy": foreground_bbox(image),
        "regions": regions,
        "score_map": full_map,
        "small_score_map": small_map,
        "model_version": metadata["model_version"],
        "model_mode": metadata["model_mode"],
        "normal_bank_sha256": metadata["normal_bank_sha256"],
    }


def extract_regions(score_map: np.ndarray, pixel_threshold: float, source_size: tuple[int, int]) -> list[dict]:
    hot = np.where(score_map > pixel_threshold, 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    hot = cv2.morphologyEx(hot, cv2.MORPH_OPEN, kernel)
    hot = cv2.morphologyEx(hot, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(hot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    source_w, source_h = source_size
    map_h, map_w = score_map.shape
    regions = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < 3.0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        x1 = max(0, int(np.floor(x * source_w / map_w)))
        y1 = max(0, int(np.floor(y * source_h / map_h)))
        x2 = min(source_w, int(np.ceil((x + w) * source_w / map_w)))
        y2 = min(source_h, int(np.ceil((y + h) * source_h / map_h)))
        roi = score_map[y:y + h, x:x + w]
        polygon = [[int(round(pt[0][0] * source_w / map_w)), int(round(pt[0][1] * source_h / map_h))] for pt in cv2.approxPolyDP(contour, 2.0, True)]
        regions.append({
            "bbox_xyxy": [x1, y1, x2, y2],
            "polygon_xy": polygon,
            "area_px_at_feature_grid": round(area, 2),
            "mean_score": round(float(np.mean(roi)), 5),
            "max_score": round(float(np.max(roi)), 5),
        })
    regions.sort(key=lambda item: item["max_score"], reverse=True)
    return regions[:8]


def render_evidence(image: np.ndarray, score_map: np.ndarray, pixel_threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scaled = np.clip(score_map / max(pixel_threshold * 2.0, 1e-6) * 255.0, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    heat = cv2.resize(heat, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    overlay = cv2.addWeighted(image, 0.58, heat, 0.42, 0)
    return heat, overlay, scaled
