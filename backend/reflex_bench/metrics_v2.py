"""Additive REFLEX pixel metric revision; frozen metrics.py stays unchanged.

AU-PRO uses every unique float32 score event, eight-connected ground-truth
regions with equal region weights, and a global false-positive denominator
including normal images. The ordered curve keeps vertical transitions.
Trapezoidal integration clips the crossing segment linearly at FPR 0.30,
then divides by 0.30. This is an explicit metric convention, not a claim of
byte-verified publisher evaluation-code parity.
"""

from __future__ import annotations

import cv2
import numpy as np

from reflex_bench.metrics import average_precision, binary_auroc


AUPRO_METHOD = "exact_float32_score_events_8connected_linear_clip_v2"


def pro_curve(mask_score_pairs: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray] | None:
    """Return threshold-ordered (FPR, PRO), or None without both populations.

    Pixels with equal scores enter together. Different scores that produce
    the same FPR remain separate points: removing either endpoint of a
    vertical segment changes the area of the preceding or next segment.
    """
    scores = []
    negative_flags = []
    region_weights = []
    region_count = 0
    negative_count = 0
    for mask, score_map in mask_score_pairs:
        truth = np.asarray(mask) > 0
        score = np.asarray(score_map, dtype=np.float32)
        if truth.ndim != 2 or truth.shape != score.shape or not truth.size:
            raise ValueError("mask and score map must be nonempty matching 2D arrays")
        if not np.isfinite(score).all():
            raise ValueError("score maps must be finite")
        count, labels = cv2.connectedComponents(truth.astype(np.uint8), connectivity=8)
        weights = np.zeros(truth.shape, dtype=np.float64)
        sizes = np.bincount(labels.ravel(), minlength=count)
        if count > 1:
            inverse_sizes = np.zeros(count, dtype=np.float64)
            inverse_sizes[1:] = 1.0 / sizes[1:]
            weights = inverse_sizes[labels]
        region_count += count - 1
        negative_count += int(np.count_nonzero(~truth))
        scores.append(score.ravel())
        negative_flags.append((~truth).ravel())
        region_weights.append(weights.ravel())
    if region_count == 0 or negative_count == 0:
        return None
    all_scores = np.concatenate(scores)
    negatives = np.concatenate(negative_flags)
    weights = np.concatenate(region_weights)
    order = np.argsort(-all_scores, kind="stable")
    sorted_scores = all_scores[order]
    group_ends = np.r_[np.flatnonzero(sorted_scores[1:] != sorted_scores[:-1]), sorted_scores.size - 1]
    false_positives = np.cumsum(negatives[order], dtype=np.uint64)[group_ends]
    region_recall = np.cumsum(weights[order], dtype=np.float64)[group_ends]
    fpr = false_positives.astype(np.float64) / negative_count
    pro = np.clip(region_recall / region_count, 0.0, 1.0)
    return np.r_[0.0, fpr, 1.0], np.r_[0.0, pro, 1.0]


def integrate_pro(fpr: np.ndarray, pro: np.ndarray, fpr_limit: float = 0.30) -> float:
    """Integrate an ordered curve, preserving repeated FPR endpoints."""
    if not np.isfinite(fpr_limit) or not 0 < fpr_limit <= 1:
        raise ValueError("fpr_limit must be in (0, 1]")
    x = np.asarray(fpr, dtype=np.float64)
    y = np.asarray(pro, dtype=np.float64)
    if x.ndim != 1 or x.size < 2 or x.shape != y.shape:
        raise ValueError("curve arrays must be matching 1D arrays with >=2 points")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(np.diff(x) < 0):
        raise ValueError("curve must be finite with nondecreasing FPR")
    if x[0] != 0 or x[-1] != 1 or np.any((y < 0) | (y > 1)):
        raise ValueError("curve must span FPR 0 to 1 with PRO in [0, 1]")
    end = int(np.searchsorted(x, fpr_limit, side="right"))
    clipped_x = x[:end]
    clipped_y = y[:end]
    if clipped_x[-1] < fpr_limit:
        # end is the first event beyond the limit, before any vertical rise
        # at that event's FPR. Do not collapse equal-FPR points before this.
        fraction = (fpr_limit - x[end - 1]) / (x[end] - x[end - 1])
        at_limit = y[end - 1] + fraction * (y[end] - y[end - 1])
        clipped_x = np.r_[clipped_x, fpr_limit]
        clipped_y = np.r_[clipped_y, at_limit]
    return float(np.trapezoid(clipped_y, clipped_x) / fpr_limit)


def au_pro(mask_score_pairs: list[tuple[np.ndarray, np.ndarray]], fpr_limit: float = 0.30) -> float | None:
    if not np.isfinite(fpr_limit) or not 0 < fpr_limit <= 1:
        raise ValueError("fpr_limit must be in (0, 1]")
    curve = pro_curve(mask_score_pairs)
    return None if curve is None else integrate_pro(*curve, fpr_limit=fpr_limit)


def pixel_metrics(mask_score_pairs: list[tuple[np.ndarray, np.ndarray]], threshold: float) -> dict:
    """Preserve legacy non-PRO definitions, replace only the AU-PRO method.

    Binary AUROC and AP call the frozen legacy functions. Threshold counts,
    ratios, and empty-population keys follow the frozen implementation.
    The additive method field makes the changed AU-PRO convention visible.
    """
    if not mask_score_pairs:
        return {"pixel_image_count": 0, "pixel_sample_count": 0, "pixel_auroc": None, "pixel_average_precision": None, "au_pro_fpr_0_30": None, "au_pro_method": AUPRO_METHOD}
    labels = []
    scores = []
    for mask, score_map in mask_score_pairs:
        truth = np.asarray(mask) > 0
        score = np.asarray(score_map, dtype=np.float32)
        if truth.ndim != 2 or truth.shape != score.shape or not truth.size:
            raise ValueError("mask and score map must be nonempty matching 2D arrays")
        if not np.isfinite(score).all():
            raise ValueError("score maps must be finite")
        labels.append(truth.astype(np.uint8).ravel())
        scores.append(score.ravel())
    y_true = np.concatenate(labels)
    y_score = np.concatenate(scores)
    pred = y_score > float(threshold)
    tp = int(np.sum(pred & (y_true == 1)))
    fp = int(np.sum(pred & (y_true == 0)))
    fn = int(np.sum((~pred) & (y_true == 1)))
    tn = int(np.sum((~pred) & (y_true == 0)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "pixel_auroc": binary_auroc(y_true, y_score),
        "pixel_average_precision": average_precision(y_true, y_score),
        "pixel_iou_at_frozen_normal_threshold": tp / max(tp + fp + fn, 1),
        "pixel_dice_at_frozen_normal_threshold": 2 * tp / max(2 * tp + fp + fn, 1),
        "pixel_precision": precision,
        "pixel_recall": recall,
        "pixel_confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "pixel_sample_count": int(y_true.size),
        "pixel_image_count": len(mask_score_pairs),
        "au_pro_fpr_0_30": au_pro(mask_score_pairs),
        "pixel_threshold": float(threshold),
        "au_pro_method": AUPRO_METHOD,
    }
