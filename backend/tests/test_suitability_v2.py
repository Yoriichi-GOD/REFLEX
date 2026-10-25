import copy
import json

import cv2
import numpy as np
import pytest

from app.core.suitability_v2 import CHECKS, _features, fit_suitability, inspect_suitability


def _texture(seed, shape=(128, 160, 3)):
    rng = np.random.default_rng(seed)
    image = np.clip(rng.normal(75, 20, shape), 0, 255).astype(np.uint8)
    cv2.ellipse(image, (shape[1] // 2, shape[0] // 2), (35, 25), 15, 0, 360, (180 + seed % 20, 190, 220), -1)
    noise = rng.integers(0, 8, shape, dtype=np.uint8)
    return cv2.add(image, noise)


@pytest.fixture(scope="module")
def normal_paths(tmp_path_factory):
    directory = tmp_path_factory.mktemp("suitability")
    paths = []
    for i in range(68):
        path = directory / f"normal-{i}.png"
        assert cv2.imwrite(str(path), _texture(i))
        paths.append(path)
    return paths[:8], paths[8:]


def test_fit_is_content_deterministic_json_serializable_and_has_no_ground_truth(normal_paths):
    fit, calibration = normal_paths
    first = fit_suitability(fit, calibration, profile="test-profile")
    second = fit_suitability(reversed(fit), reversed(calibration), profile="test-profile")
    assert first == second
    assert json.loads(json.dumps(first, allow_nan=False)) == first
    assert first["fit_count"] == 8 and first["calibration_count"] == 60
    assert not (set(first["fit_sha256"]) & set(first["calibration_sha256"]))
    assert first["calibration_can_flag"]


def test_metadata_tamper_and_unsupported_version_rejected(normal_paths):
    fit, calibration = normal_paths
    metadata = fit_suitability(fit, calibration)
    changed = copy.deepcopy(metadata)
    changed["alpha"] = .99
    with pytest.raises(ValueError, match="integrity"):
        inspect_suitability(_texture(99), changed)
    changed["version"] = "invented"
    with pytest.raises(ValueError, match="Unsupported"):
        inspect_suitability(_texture(99), changed)


def test_duplicate_content_and_overlap_rejected_before_decode(normal_paths, tmp_path):
    fit, calibration = normal_paths
    duplicate = tmp_path / "renamed.png"
    duplicate.write_bytes(fit[0].read_bytes())
    with pytest.raises(ValueError, match="unique and disjoint"):
        fit_suitability(fit, [duplicate, *calibration])
    with pytest.raises(ValueError, match="unique and disjoint"):
        fit_suitability([fit[0], *fit], calibration)


@pytest.mark.parametrize("position", [(20, 20), (100, 20), (20, 80), (100, 80)])
def test_uniform_patch_clue_searches_locations_without_center_prior(position):
    image = np.random.default_rng(21).integers(20, 150, (128, 160, 3), dtype=np.uint8)
    x, y = position
    image[y:y + 24, x:x + 24] = 65
    result = _features(image)
    assert result["flat_internal_region_score"] > 0
    box = result["flat_candidate"]["bbox_normalized"]
    assert x / 160 <= box[0] <= (x + 4) / 160
    assert y / 128 <= box[1] <= (y + 4) / 128


def test_runtime_only_warns_and_tail_ranks_are_reproducible(normal_paths):
    fit, calibration = normal_paths
    metadata = fit_suitability(fit, calibration, profile="test")
    image = _texture(100)
    result = inspect_suitability(image, metadata)
    repeated = inspect_suitability(image, json.loads(json.dumps(metadata)))
    assert result == repeated
    assert result["disposition"] == "WARNING_ONLY"
    assert result["warning_count_is_defect_detection"] is False
    assert result["complete_visibility_certified"] is False
    assert result["semantic_profile_identity_certified"] is False
    assert set(result["calibrated_p_values"]) == set(CHECKS)
    for name, score in result["scores"].items():
        expected = (1 + sum(value >= score for value in metadata["calibration_scores"][name])) / 61
        assert result["calibrated_p_values"][name] == pytest.approx(expected)
    assert result["flags"] == [name for name in CHECKS if result["calibrated_p_values"][name] <= .05 / 3]


def test_small_calibration_warns_it_cannot_resolve_requested_tail(normal_paths):
    fit, calibration = normal_paths
    metadata = fit_suitability(fit, calibration[:20])
    assert metadata["calibration_can_flag"] is False
    result = inspect_suitability(np.full((128, 160, 3), 255, dtype=np.uint8), metadata)
    assert not result["flags"]
    assert result["calibration_can_flag"] is False


@pytest.mark.parametrize("image", [np.zeros((12, 12), np.uint8), np.zeros((12, 12, 3), np.float32), np.zeros((0, 12, 3), np.uint8), np.zeros((7, 12, 3), np.uint8)])
def test_invalid_images_fail_explicitly(image):
    with pytest.raises(ValueError):
        _features(image)


def test_insufficient_fit_and_invalid_alpha_rejected(normal_paths):
    fit, calibration = normal_paths
    with pytest.raises(ValueError, match=">=8"):
        fit_suitability(fit[:7], calibration)
    with pytest.raises(ValueError, match="alpha"):
        fit_suitability(fit, calibration, alpha=0)


def test_no_largest_object_heuristic():
    image = np.zeros((256, 256, 3), np.uint8)
    for x, y in ((70, 70), (185, 70), (70, 185), (185, 185)):
        cv2.circle(image, (x, y), 35, (200, 200, 200), -1)
    features = _features(image)
    assert features["foreground_components_over_half_percent"] == 4


def test_large_border_connected_flat_background_not_an_internal_hole():
    image = np.full((128, 160, 3), 50, np.uint8)
    features = _features(image)
    assert features["flat_candidate"] is None
    assert features["flat_internal_region_score"] == 0
