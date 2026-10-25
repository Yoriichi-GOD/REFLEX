import numpy as np

from reflex_bench.metrics import average_precision, binary_auroc, decision_metrics, pixel_metrics, threshold_metrics
from reflex_bench.robustness import _variants


def test_auc_with_ties_and_average_precision_known_values():
    labels = np.asarray([0, 1, 0, 1], dtype=np.uint8)
    scores = np.asarray([0.1, 0.4, 0.35, 0.8], dtype=np.float64)
    assert binary_auroc(labels, scores) == 1.0
    assert average_precision(labels, scores) == 1.0
    assert binary_auroc(np.asarray([0, 1]), np.asarray([0.5, 0.5])) == 0.5


def test_frozen_threshold_confusion_matrix():
    result = threshold_metrics(np.asarray([0, 0, 1, 1]), np.asarray([0.1, 0.8, 0.7, 0.9]), 0.75)
    assert result["confusion_matrix"] == {"TP": 1, "FP": 1, "FN": 1, "TN": 1}
    assert result["recall"] == 0.5
    assert result["false_positive_rate_on_negatives"] == 0.5


def test_abstentions_are_excluded_from_resolved_coverage_denominator():
    result = decision_metrics(np.asarray([0, 1, 1]), ["PASS", "DEFECT_FOUND", "NEEDS_REVIEW"])
    assert result["coverage"] == 2 / 3
    assert result["abstention_count"] == 1
    assert result["confusion_matrix_on_resolved"] == {"TP": 1, "FP": 0, "FN": 0, "TN": 1}


def test_pixel_metrics_and_region_pro_are_finite():
    truth = np.zeros((8, 8), dtype=np.uint8); truth[2:4, 2:4] = 1
    scores = np.zeros((8, 8), dtype=np.float32); scores[2:4, 2:4] = 1.0
    result = pixel_metrics([(truth, scores)], threshold=0.5)
    assert result["pixel_auroc"] == 1.0
    assert result["pixel_average_precision"] == 1.0
    assert result["pixel_iou_at_frozen_normal_threshold"] == 1.0
    assert 0.0 <= result["au_pro_fpr_0_30"] <= 1.0


def test_defect_downsize_perturbation_reduces_mask_area_without_shape_change():
    yy, xx = np.indices((64, 64))
    image = np.stack((xx * 3, yy * 3, (xx + yy) * 2), axis=2).clip(0, 255).astype(np.uint8)
    mask = np.zeros((64, 64), dtype=np.uint8); mask[24:40, 24:40] = 1
    transformed, transformed_mask = _variants(image, mask, 5)["defect_downsize_0_5"]
    assert transformed.shape == image.shape
    assert transformed_mask.shape == mask.shape
    assert 0 < transformed_mask.sum() < mask.sum() * 0.35
