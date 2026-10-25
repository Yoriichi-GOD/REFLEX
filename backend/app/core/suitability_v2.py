"""Normal-calibrated capture *warnings*, separate from anomaly disposition.

No ground-truth mask, filename, test label or expected object count is accepted by
the runtime API. A warning is unresolved capture evidence, never a defect hit.
This module deliberately makes no claim to certify complete visibility.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

VERSION = "reflex-suitability-2.0"
CHECKS = ("FLAT_INTERNAL_REGION", "FIELD_OF_VIEW_SHIFT", "PROFILE_DISTRIBUTION_SHIFT")
MAX_SIDE = 256


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _small(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected a nonempty uint8 BGR image with three channels")
    if min(image.shape[:2]) < 8:
        raise ValueError("Image sides must both be at least eight pixels")
    scale = min(1.0, MAX_SIDE / max(image.shape[:2]))
    return cv2.resize(image, (max(8, round(image.shape[1] * scale)), max(8, round(image.shape[0] * scale))), interpolation=cv2.INTER_AREA)


def _features(image: np.ndarray) -> dict:
    small = _small(image)
    h, w = small.shape[:2]
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    # All bright connected objects survive; no largest-box crop is used.
    _, foreground = cv2.threshold(lab[:, :, 0], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = foreground.astype(bool)
    ys, xs = np.nonzero(mask)
    area = float(mask.mean())
    edge = max(1, round(min(h, w) * .02))
    side_contact = [float(mask[:, :edge].mean()), float(mask[:, -edge:].mean()),
                    float(mask[:edge].mean()), float(mask[-edge:].mean())]
    if len(xs):
        bbox = [float(xs.min() / w), float(ys.min() / h), float((xs.max() + 1) / w), float((ys.max() + 1) / h)]
        center = [float(xs.mean() / w), float(ys.mean() / h)]
    else:
        bbox, center = [0.0, 0.0, 0.0, 0.0], [.5, .5]
    n, _, stats, _ = cv2.connectedComponentsWithStats(foreground, 8)
    count = int(sum(stats[i, cv2.CC_STAT_AREA] >= .005 * h * w for i in range(1, n)))
    view = np.asarray([area, *side_contact, *bbox, *center, min(count, 20) / 20], np.float64)

    # Search every location. Internal constant/near-constant regions are one
    # occlusion clue, not an occlusion semantic classifier. Border components
    # are excluded because normal backgrounds are often smooth and unbounded.
    local_range = cv2.dilate(small, np.ones((5, 5), np.uint8)).astype(np.int16) - cv2.erode(small, np.ones((5, 5), np.uint8)).astype(np.int16)
    flat = (np.max(local_range, axis=2) <= 3).astype(np.uint8)
    nc, labels, cs, _ = cv2.connectedComponentsWithStats(flat, 8)
    candidate = None
    best = 0.0
    for i in range(1, nc):
        x, y, cw, ch, pixels = [int(v) for v in cs[i]]
        if x == 0 or y == 0 or x + cw >= w or y + ch >= h or pixels < max(9, .0004 * h * w):
            continue
        component = (labels == i).astype(np.uint8)
        ring = (cv2.dilate(component, np.ones((7, 7), np.uint8)) > 0) & (component == 0)
        if not ring.any():
            continue
        inside = small[component > 0].mean(axis=0)
        contrast = float(np.linalg.norm(small[ring].mean(axis=0) - inside) / (255 * np.sqrt(3)))
        rectangularity = pixels / (cw * ch)
        # Size, rectangular support and boundary contrast vary continuously.
        score = float((pixels / (h * w)) * rectangularity * (1.0 - np.exp(-contrast / .03)))
        if score > best:
            best = score
            candidate = {"bbox_normalized": [x / w, y / h, (x + cw) / w, (y + ch) / h],
                         "area_fraction": pixels / (h * w), "rectangularity": rectangularity,
                         "boundary_contrast": contrast}
    # Global color and coarse all-object layout provide a profile-distribution
    # check. They do not prove the selected category is the object's identity.
    hist = []
    for c, bins in ((0, 16), (1, 8), (2, 8)):
        hist.extend((np.histogram(lab[:, :, c], bins=bins, range=(0, 256))[0] / (h * w)).tolist())
    layout = cv2.resize(foreground.astype(np.float32) / 255, (4, 4), interpolation=cv2.INTER_AREA).ravel()
    descriptor = np.asarray([*hist, *layout, *view], np.float64)
    return {"flat_internal_region_score": best, "flat_candidate": candidate,
            "view_descriptor": view, "profile_descriptor": descriptor,
            "foreground_area_fraction": area, "foreground_border_contact": side_contact,
            "foreground_components_over_half_percent": count, "analysis_shape": [h, w],
            "source_shape": [int(image.shape[0]), int(image.shape[1])]}


def _robust_parameters(values: np.ndarray, floor: float) -> tuple[np.ndarray, np.ndarray]:
    center = np.median(values, axis=0)
    scale = np.maximum(np.median(np.abs(values - center), axis=0) * 1.4826, floor)
    return center, scale


def _scores(features: dict, metadata: dict) -> list[float]:
    view = np.asarray(features["view_descriptor"], np.float64)
    view_center = np.asarray(metadata["view_center"], np.float64)
    view_scale = np.asarray(metadata["view_scale"], np.float64)
    view_score = float(np.sqrt(np.mean(((view - view_center) / view_scale) ** 2)))
    descriptor = np.asarray(features["profile_descriptor"], np.float64)
    center = np.asarray(metadata["profile_center"], np.float64)
    scale = np.asarray(metadata["profile_scale"], np.float64)
    references = np.asarray(metadata["profile_references"], np.float64)
    normalized = (descriptor - center) / scale
    profile_score = float(np.sqrt(np.min(np.mean((references - normalized) ** 2, axis=1))))
    return [float(features["flat_internal_region_score"]), view_score, profile_score]


def _read(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image {path}")
    return image


def fit_suitability(fitting_paths: Iterable[str | Path], calibration_paths: Iterable[str | Path] | None = None,
                    *, profile: str | None = None, alpha: float = .05) -> dict:
    """Fit normal-only descriptors and disjoint empirical calibration tails.

    If calibration paths are omitted, a deterministic content-hash ordering
    reserves every fifth image. Caller is responsible for supplying normals.
    Duplicate file bytes and overlapping fit/calibration content are rejected.
    The returned metadata is JSON serializable, without arrays or local paths.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    fitting = [Path(p) for p in fitting_paths]
    if calibration_paths is None:
        fitting = sorted(fitting, key=lambda p: (_digest(p), p.name))
        calibration = fitting[::5]
        fitting = [p for i, p in enumerate(fitting) if i % 5]
    else:
        calibration = [Path(p) for p in calibration_paths]
    if len(fitting) < 8 or len(calibration) < 20:
        raise ValueError("Need >=8 normal fitting and >=20 disjoint normal calibration images")
    fit_items = sorted([(_digest(p), p) for p in fitting], key=lambda item: item[0])
    cal_items = sorted([(_digest(p), p) for p in calibration], key=lambda item: item[0])
    all_hashes = [digest for digest, _ in fit_items + cal_items]
    if len(set(all_hashes)) != len(all_hashes):
        raise ValueError("Fitting and calibration content must be unique and disjoint")
    fit_features = [_features(_read(p)) for _, p in fit_items]
    views = np.stack([f["view_descriptor"] for f in fit_features])
    descriptors = np.stack([f["profile_descriptor"] for f in fit_features])
    vc, vs = _robust_parameters(views, .02)
    pc, ps = _robust_parameters(descriptors, .02)
    metadata = {"version": VERSION, "profile": profile, "alpha": float(alpha), "max_side": MAX_SIDE,
                "checks": list(CHECKS), "multiple_check_control": "Bonferroni alpha / 3, empirical upper-tail p=(1+count(cal>=score))/(n+1)",
                "view_center": vc.tolist(), "view_scale": vs.tolist(),
                "profile_center": pc.tolist(), "profile_scale": ps.tolist(),
                "profile_references": ((descriptors - pc) / ps).tolist(),
                "fit_sha256": [h for h, _ in fit_items], "calibration_sha256": [h for h, _ in cal_items],
                "fit_count": len(fitting), "calibration_count": len(calibration),
                "supported_scope": "appearance-distribution warnings; complete visibility and semantic identity are not certified",
                "calibration_assumption": "normal images exchangeable with intended suitable captures; unverified for new physical captures"}
    calibration_scores = [_scores(_features(_read(p)), metadata) for _, p in cal_items]
    metadata["calibration_scores"] = {name: sorted(float(row[i]) for row in calibration_scores) for i, name in enumerate(CHECKS)}
    metadata["minimum_p_value"] = 1 / (len(calibration) + 1)
    metadata["check_alpha"] = float(alpha / len(CHECKS))
    metadata["calibration_can_flag"] = metadata["minimum_p_value"] <= metadata["check_alpha"]
    metadata["metadata_sha256"] = hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return metadata


def inspect_suitability(image: np.ndarray, metadata: dict) -> dict:
    """Return calibrated warning clues; never return a detector disposition.

    Empty flags mean no measured distribution warning, *not* full visibility.
    p-values are normal-tail ranks, not probabilities a capture is suitable.
    """
    if metadata.get("version") != VERSION or metadata.get("checks") != list(CHECKS) or metadata.get("max_side") != MAX_SIDE:
        raise ValueError("Unsupported suitability metadata version/configuration")
    candidate = {k: v for k, v in metadata.items() if k != "metadata_sha256"}
    actual = hashlib.sha256(json.dumps(candidate, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if actual != metadata.get("metadata_sha256"):
        raise ValueError("Suitability metadata integrity check failed")
    features = _features(image)
    scores = _scores(features, metadata)
    p_values = {}
    for name, score in zip(CHECKS, scores):
        calibration = np.asarray(metadata["calibration_scores"][name], np.float64)
        p_values[name] = float((1 + np.count_nonzero(calibration >= score)) / (len(calibration) + 1))
    flags = [name for name in CHECKS if p_values[name] <= metadata["check_alpha"]]
    public_features = {k: v for k, v in features.items() if k not in ("view_descriptor", "profile_descriptor")}
    return {"version": VERSION, "profile": metadata["profile"], "flags": flags,
            "routing_flags": [], "routing_authorized": False,
            "features": public_features, "scores": dict(zip(CHECKS, scores)),
            "calibrated_p_values": p_values, "alpha": metadata["alpha"], "per_check_alpha": metadata["check_alpha"],
            "calibration_can_flag": metadata["calibration_can_flag"], "metadata_sha256": metadata["metadata_sha256"],
            "complete_visibility_certified": False, "semantic_profile_identity_certified": False,
            "disposition": "WARNING_ONLY", "warning_count_is_defect_detection": False}
