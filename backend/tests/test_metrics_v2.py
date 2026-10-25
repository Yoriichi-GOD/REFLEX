"""Known-answer regression tests; no model or evaluation data is accessed."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

try:
    from reflex_bench import metrics_v2 as revised
except ImportError:
    spec = importlib.util.spec_from_file_location("metrics_v2_audit", Path(__file__).with_name("metrics_v2.py"))
    revised = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revised)
from reflex_bench import metrics as legacy


def synthetic_cases():
    mask = np.zeros((8, 8), np.uint8)
    mask[2:4, 2:4] = 1
    large = np.zeros((16, 16), np.uint8)
    large[1, 1] = 1
    large[8:12, 8:12] = 1
    unequal_score = np.full((16, 16), .5, np.float32)
    unequal_score[1, 1] = .9
    unequal_score[8:12, 8:12] = .1
    diagonal = np.zeros_like(mask)
    diagonal[2, 2] = diagonal[3, 3] = 1
    diagonal_score = np.full(mask.shape, .5, np.float32)
    diagonal_score[2, 2] = .9
    diagonal_score[3, 3] = .1
    random_masks = [np.zeros((12, 14), np.uint8) for _ in range(3)]
    random_masks[0][1:3, 1:4] = 1
    random_masks[1][2, 2] = 1
    random_masks[1][6:10, 8:12] = 1
    rng = np.random.default_rng(37)
    random_maps = [rng.random((12, 14), dtype=np.float32) for _ in random_masks]
    return {
        "perfect": [(mask, np.where(mask, .9, .1).astype(np.float32))],
        "reversed": [(mask, np.where(mask, .1, .9).astype(np.float32))],
        "constant": [(mask, np.full(mask.shape, .5, np.float32))],
        "partial_ties": [(mask, (np.arange(64).reshape(8, 8) % 4).astype(np.float32) / 4)],
        "unequal_regions": [(large, unequal_score)],
        "diagonal_component": [(diagonal, diagonal_score)],
        "mixed_normal_images": [(mask, np.where(mask, .9, .1).astype(np.float32)), (np.zeros_like(mask), np.full(mask.shape, .8, np.float32))],
        "random_continuous_seed37": list(zip(random_masks, random_maps)),
        "random_tied_seed37": [(m, (s * 8).astype(np.uint8).astype(np.float32) / 8) for m, s in zip(random_masks, random_maps)],
    }


@pytest.mark.parametrize("name,expected", [("perfect", 1.), ("reversed", 0.), ("constant", .15), ("unequal_regions", .5), ("diagonal_component", .5), ("mixed_normal_images", 1.)])
def test_analytic_cases(name, expected):
    assert revised.au_pro(synthetic_cases()[name]) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("limit", [.1, .3, .5, 1.])
def test_crossing_segment_interpolation_and_normalization(limit):
    assert revised.integrate_pro(np.array([0., 1.]), np.array([0., 1.]), limit) == pytest.approx(limit / 2, abs=1e-12)


def test_partial_segment_and_vertical_endpoint():
    assert revised.integrate_pro(np.array([0., .6, 1.]), np.array([0., .8, 1.]), .3) == pytest.approx(.2)
    assert revised.integrate_pro(np.array([0., .6, .6, 1.]), np.array([0., 0., 1., 1.]), .3) == 0.
    assert revised.integrate_pro(np.array([0., .3, .3, 1.]), np.array([0., 0., 1., 1.]), .3) == 0.


def test_reversed_curve_keeps_both_vertical_endpoints():
    x, y = revised.pro_curve(synthetic_cases()["reversed"])
    np.testing.assert_array_equal(x, [0, 1, 1, 1])
    np.testing.assert_array_equal(y, [0, 0, 1, 1])


@pytest.mark.parametrize("name", list(synthetic_cases()))
def test_non_pro_pixel_outputs_match_frozen_legacy(name):
    pairs = synthetic_cases()[name]
    before = legacy.pixel_metrics(pairs, .55)
    after = revised.pixel_metrics(pairs, .55)
    for key, value in before.items():
        if key != "au_pro_fpr_0_30":
            assert after[key] == value, key
    assert after["au_pro_method"] == revised.AUPRO_METHOD


@pytest.mark.parametrize("name", list(synthetic_cases()))
def test_positive_monotone_scaling_and_image_order(name):
    pairs = synthetic_cases()[name]
    # Scaling by a power of two preserves the exact float32 score order.
    scaled = [(m, s * 2) for m, s in pairs]
    assert revised.au_pro(pairs) == pytest.approx(revised.au_pro(scaled), abs=1e-12)
    assert revised.au_pro(pairs) == pytest.approx(revised.au_pro(list(reversed(pairs))), abs=1e-12)


def test_absent_populations_are_undefined():
    assert revised.au_pro([]) is None
    assert revised.au_pro([(np.zeros((4, 4)), np.ones((4, 4)))]) is None
    assert revised.au_pro([(np.ones((4, 4)), np.ones((4, 4)))]) is None


@pytest.mark.parametrize("limit", [0, -1, 1.1, float("nan")])
def test_invalid_limit_rejected(limit):
    with pytest.raises(ValueError):
        revised.au_pro(synthetic_cases()["perfect"], limit)


@pytest.mark.parametrize("invalid", [np.full((8, 8), np.nan), np.full((8, 8), np.inf), np.zeros((2, 2))])
def test_invalid_map_rejected(invalid):
    mask = synthetic_cases()["perfect"][0][0]
    with pytest.raises(ValueError):
        revised.au_pro([(mask, invalid)])


def test_varying_map_shapes_supported():
    pairs = synthetic_cases()["perfect"]
    pairs = pairs + [(np.zeros((2, 3)), np.full((2, 3), .2, np.float32))]
    assert revised.au_pro(pairs) == pytest.approx(1.)
