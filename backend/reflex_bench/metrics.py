"""Metrics used by the REFLEX benchmark protocol.

Pixel maps are evaluated at a documented, aspect-preserving maximum side of
256 pixels. Region PRO follows connected ground-truth components and global
false-positive rate over normal pixels; all thresholds are derived from the
prediction maps, never from test labels.
"""

from __future__ import annotations

import cv2
import numpy as np


def _arrays(labels: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(labels, dtype=np.uint8).ravel()
    s = np.asarray(scores, dtype=np.float64).ravel()
    if y.size != s.size:
        raise ValueError("labels and scores must have equal size")
    if y.size == 0:
        raise ValueError("labels and scores must be non-empty")
    if not np.isin(y, (0, 1)).all():
        raise ValueError("labels must contain only 0 and 1")
    if not np.isfinite(s).all():
        raise ValueError("scores must be finite")
    return y, s


def binary_auroc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    y, s = _arrays(labels, scores)
    positives = int(y.sum())
    negatives = int(y.size - positives)
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(-s, kind="mergesort")
    sorted_scores = s[order]
    sorted_labels = y[order]
    group_ends = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(sorted_scores) - 1]
    tp = np.cumsum(sorted_labels, dtype=np.int64)[group_ends]
    fp = group_ends + 1 - tp
    tpr = np.r_[0.0, tp / positives]
    fpr = np.r_[0.0, fp / negatives]
    return float(np.trapezoid(tpr, fpr))


def average_precision(labels: np.ndarray, scores: np.ndarray) -> float | None:
    y, s = _arrays(labels, scores)
    positives = int(y.sum())
    if positives == 0:
        return None
    order = np.argsort(-s, kind="mergesort")
    sorted_scores = s[order]
    sorted_labels = y[order]
    group_ends = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(sorted_scores) - 1]
    tp = np.cumsum(sorted_labels, dtype=np.int64)[group_ends]
    fp = group_ends + 1 - tp
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / positives
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


def threshold_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    y, s = _arrays(labels, scores)
    pred = s > float(threshold)
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum((~pred) & (y == 1)))
    tn = int(np.sum((~pred) & (y == 0)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "sample_count": int(y.size),
        "positive_count": int(np.sum(y == 1)),
        "negative_count": int(np.sum(y == 0)),
        "auroc": binary_auroc(y, s),
        "average_precision": average_precision(y, s),
        "threshold": float(threshold),
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "false_positive_rate_on_negatives": fp / max(fp + tn, 1),
        "predictions": pred.astype(np.uint8),
    }


def decision_metrics(labels: np.ndarray, decisions: list[str]) -> dict:
    y = np.asarray(labels, dtype=np.uint8).ravel()
    if len(y) != len(decisions):
        raise ValueError("labels and decisions must have equal size")
    pred_map = {"PASS": 0, "DEFECT_FOUND": 1}
    resolved = [(int(label), pred_map.get(str(decision))) for label, decision in zip(y, decisions)]
    resolved = [(label, pred) for label, pred in resolved if pred is not None]
    if not resolved:
        tp = fp = fn = tn = 0
    else:
        labels_r = np.asarray([p[0] for p in resolved], dtype=np.uint8)
        pred_r = np.asarray([p[1] for p in resolved], dtype=np.uint8)
        tp = int(np.sum((labels_r == 1) & (pred_r == 1)))
        fp = int(np.sum((labels_r == 0) & (pred_r == 1)))
        fn = int(np.sum((labels_r == 1) & (pred_r == 0)))
        tn = int(np.sum((labels_r == 0) & (pred_r == 0)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    abstentions = int(len(y) - len(resolved))
    return {
        "sample_count": int(len(y)),
        "resolved_count": int(len(resolved)),
        "abstention_count": abstentions,
        "coverage": len(resolved) / max(len(y), 1),
        "confusion_matrix_on_resolved": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision_on_resolved": precision,
        "recall_on_resolved": recall,
        "f1_on_resolved": 2 * precision * recall / max(precision + recall, 1e-12),
        "false_clear_count": int(sum(label == 1 and decision == "PASS" for label, decision in zip(y, decisions))),
        "false_defect_count": int(sum(label == 0 and decision == "DEFECT_FOUND" for label, decision in zip(y, decisions))),
        "needs_review_count": int(sum(decision == "NEEDS_REVIEW" for decision in decisions)),
        "needs_input_count": int(sum(decision == "NEEDS_INPUT" for decision in decisions)),
    }


def _au_pro(mask_score_pairs: list[tuple[np.ndarray, np.ndarray]], fpr_limit: float = 0.30, num_thresholds: int = 200) -> float | None:
    normal_scores: list[np.ndarray] = []
    components: list[np.ndarray] = []
    all_min = float("inf")
    all_max = float("-inf")
    for mask, score_map in mask_score_pairs:
        truth = np.asarray(mask) > 0
        score = np.asarray(score_map, dtype=np.float32)
        if truth.shape != score.shape:
            raise ValueError("mask and score map shapes must match for AU-PRO")
        if not np.isfinite(score).all():
            raise ValueError("score maps must be finite")
        all_min = min(all_min, float(score.min()))
        all_max = max(all_max, float(score.max()))
        normal_scores.append(score[~truth].astype(np.float64, copy=False))
        count, component_map = cv2.connectedComponents(truth.astype(np.uint8), connectivity=8)
        for component_id in range(1, count):
            values = score[component_map == component_id].astype(np.float64, copy=False)
            if values.size:
                components.append(np.sort(values))
    if not components or not normal_scores:
        return None
    negatives = np.concatenate([part for part in normal_scores if part.size])
    if negatives.size == 0 or all_max <= all_min:
        return None
    thresholds = np.linspace(all_max, all_min, num_thresholds, dtype=np.float64)
    thresholds = np.r_[np.nextafter(all_max, np.inf), thresholds, np.nextafter(all_min, -np.inf)]
    sorted_negatives = np.sort(negatives)
    fpr = (sorted_negatives.size - np.searchsorted(sorted_negatives, thresholds, side="right")) / sorted_negatives.size
    pro = np.zeros_like(thresholds)
    for region in components:
        pro += (region.size - np.searchsorted(region, thresholds, side="right")) / region.size
    pro /= len(components)
    order = np.argsort(fpr, kind="mergesort")
    fpr = fpr[order]
    pro = pro[order]
    unique_fpr, starts = np.unique(fpr, return_index=True)
    best_pro = np.maximum.reduceat(pro, starts)
    within = unique_fpr <= fpr_limit
    x = unique_fpr[within]
    y = best_pro[within]
    if x.size == 0 or x[0] > 0:
        x = np.r_[0.0, x]
        y = np.r_[0.0, y]
    if x[-1] < fpr_limit:
        y_limit = float(np.interp(fpr_limit, unique_fpr, best_pro)) if unique_fpr[-1] >= fpr_limit else float(y[-1])
        x = np.r_[x, fpr_limit]
        y = np.r_[y, y_limit]
    return float(np.trapezoid(y, x) / fpr_limit)


def pixel_metrics(mask_score_pairs: list[tuple[np.ndarray, np.ndarray]], threshold: float) -> dict:
    if not mask_score_pairs:
        return {"pixel_image_count": 0, "pixel_sample_count": 0, "pixel_auroc": None, "pixel_average_precision": None, "au_pro_fpr_0_30": None}
    labels: list[np.ndarray] = []
    scores: list[np.ndarray] = []
    for mask, score_map in mask_score_pairs:
        truth = np.asarray(mask) > 0
        score = np.asarray(score_map, dtype=np.float32)
        if truth.shape != score.shape:
            raise ValueError("mask and score map shapes must match")
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
        "au_pro_fpr_0_30": _au_pro(mask_score_pairs, fpr_limit=0.30),
        "pixel_threshold": float(threshold),
    }


def area_slices(labels: np.ndarray, scores: np.ndarray, thresholds: float | np.ndarray, anomaly_fractions: np.ndarray) -> dict:
    y = np.asarray(labels, dtype=np.uint8).ravel()
    s = np.asarray(scores, dtype=np.float64).ravel()
    fractions = np.asarray(anomaly_fractions, dtype=np.float64).ravel()
    limits = np.asarray(thresholds if np.ndim(thresholds) else [thresholds], dtype=np.float64).ravel()
    if len(y) != len(s) or len(y) != len(fractions):
        raise ValueError("area slice inputs must have equal size")
    bins = [("lt_0_1pct", 0.0, 0.001), ("0_1_to_1pct", 0.001, 0.01), ("1_to_5pct", 0.01, 0.05), ("ge_5pct", 0.05, float("inf"))]
    output = {}
    for name, low, high in bins:
        selected = (y == 1) & (fractions >= low) & (fractions < high)
        n = int(np.sum(selected))
        output[name] = {"anomaly_count": n, "recall_at_frozen_threshold": float(np.mean(s[selected] > limits[0])) if n else None}
    return output
