from __future__ import annotations

import cv2
import numpy as np


def align_affine(reference: np.ndarray, candidate: np.ndarray) -> tuple[np.ndarray | None, dict]:
    """Register a candidate to a same-sized reference with OpenCV ECC; reject weak transforms."""
    if reference.shape[:2] != candidate.shape[:2]:
        return None, {"accepted": False, "method": "ecc_affine", "reason": "SIZE_MISMATCH"}
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    cand_gray = cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY)
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
    try:
        correlation, warp = cv2.findTransformECC(ref_gray, cand_gray, warp, cv2.MOTION_AFFINE, criteria, None, 5)
    except cv2.error as exc:
        return None, {"accepted": False, "method": "ecc_affine", "reason": "ECC_DID_NOT_CONVERGE", "detail": str(exc).splitlines()[0]}
    linear = warp[:, :2]
    determinant = float(np.linalg.det(linear))
    translation = float(np.linalg.norm(warp[:, 2]))
    accepted = bool(correlation >= 0.72 and 0.65 <= determinant <= 1.45 and translation <= max(reference.shape[:2]) * 0.25)
    evidence = {
        "accepted": accepted, "method": "cv2.findTransformECC_affine", "correlation": float(correlation),
        "transform_2x3": warp.astype(float).tolist(), "determinant": determinant,
        "translation_pixels": translation, "reason": None if accepted else "UNSTABLE_TRANSFORM",
    }
    if not accepted:
        return None, evidence
    height, width = reference.shape[:2]
    aligned = cv2.warpAffine(candidate, warp, (width, height), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
    return aligned, evidence


def compare_aligned(reference: np.ndarray, aligned: np.ndarray) -> tuple[np.ndarray, dict]:
    ref_lab = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(np.int16)
    new_lab = cv2.cvtColor(aligned, cv2.COLOR_BGR2LAB).astype(np.int16)
    delta = np.sqrt(np.mean((ref_lab - new_lab).astype(np.float32) ** 2, axis=2))
    difference = cv2.applyColorMap(np.clip(delta * 4.0, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    return difference, {"mean_lab_delta": float(np.mean(delta)), "p95_lab_delta": float(np.percentile(delta, 95)), "pixel_count": int(delta.size)}
