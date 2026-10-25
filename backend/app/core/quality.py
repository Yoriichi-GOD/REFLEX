from __future__ import annotations

import cv2
import numpy as np


def inspect_quality(image: np.ndarray) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    height, width = gray.shape
    brightness = float(np.mean(gray))
    dynamic_range = float(np.percentile(gray, 99) - np.percentile(gray, 1))
    clipping = float(np.mean((gray <= 3) | (gray >= 252)))
    focus = float(lap.var())
    flags: list[str] = []
    if min(width, height) < 128:
        flags.append("LOW_RESOLUTION")
    if focus < 12.0:
        flags.append("LOW_FOCUS")
    if clipping > 0.28 or brightness < 8 or brightness > 247 or dynamic_range < 18:
        flags.append("EXPOSURE_LIMIT")
    ratio = max(width / max(height, 1), height / max(width, 1))
    if ratio > 5.0:
        flags.append("EXTREME_ASPECT_RATIO")
    return {
        "width": int(width), "height": int(height), "channels": 3,
        "focus_laplacian_variance": round(focus, 4),
        "brightness_mean": round(brightness, 4),
        "dynamic_range_p98_minus_p02": round(dynamic_range, 4),
        "clipped_pixel_fraction": round(clipping, 6),
        "aspect_ratio_long_over_short": round(ratio, 4),
        "quality_score": round(float(max(0.0, min(1.0, min(1.0, focus / 80.0) * (1.0 - min(clipping, 1.0))))), 4),
        "quality_score_is_calibrated": False,
        "flags": flags,
    }


def foreground_bbox(image: np.ndarray) -> list[int] | None:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness = cv2.GaussianBlur(lab[:, :, 0], (5, 5), 0)
    _, mask = cv2.threshold(lightness, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]
    candidates = [cv2.boundingRect(c) for c in contours if 0.02 < cv2.contourArea(c) / max(image_area, 1) < 0.98]
    if not candidates:
        return None
    x, y, w, h = max(candidates, key=lambda box: box[2] * box[3])
    return [int(x), int(y), int(x + w), int(y + h)]
