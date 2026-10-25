from pathlib import Path
from io import BytesIO
from uuid import uuid4

import cv2
import numpy as np
import pytest
from PIL import Image

from app.agent.controller import run_policy
from app.core.alignment import align_affine
from app.core.image_io import ImageInputError, decode_image
from app.core.model import analyze, load_bank
from app import storage
from app.config import ASSET_DIR
from scripts.evaluate_dataset import average_precision, pixel_metrics, roc_auc
from scripts.prepare_visa import prepare, resolve_dataset_file

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_is_opencv_five():
    assert cv2.__version__.split(".")[0] == "5"


def test_decode_grayscale_alpha_and_sixteen_bit():
    gray = np.full((40, 60), 120, np.uint8)
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    image, meta = decode_image(encoded.tobytes())
    assert image.shape == (40, 60, 3)
    assert meta["source_bit_depth"] == 8
    rgba = np.zeros((24, 32, 4), np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 3] = 0
    ok, encoded = cv2.imencode(".png", rgba)
    assert ok
    composite, _ = decode_image(encoded.tobytes())
    assert np.all(composite == 127)
    high = np.tile(np.arange(256, dtype=np.uint16), (32, 1))
    ok, encoded = cv2.imencode(".png", high)
    assert ok
    normalized, high_meta = decode_image(encoded.tobytes())
    assert normalized.dtype == np.uint8 and high_meta["source_bit_depth"] == 16


def test_corrupt_and_empty_image_are_rejected():
    with pytest.raises(ImageInputError, match="non-empty"):
        decode_image(b"")
    with pytest.raises(ImageInputError, match="valid PNG"):
        decode_image(b"not an image")


def test_encoded_dimensions_are_rejected_before_decode():
    header = bytearray(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + b"\x00\x00\x00\x01" + (5000).to_bytes(4, "big"))
    with pytest.raises(ImageInputError) as error:
        decode_image(bytes(header))
    assert error.value.code == "IMAGE_DIMENSIONS_EXCEEDED"


def test_exif_orientation_is_applied_after_opencv_decode():
    pil_image = Image.fromarray(np.zeros((40, 60, 3), np.uint8))
    exif = pil_image.getexif(); exif[274] = 6
    stream = BytesIO(); pil_image.save(stream, format="JPEG", exif=exif)
    image, metadata = decode_image(stream.getvalue())
    assert image.shape[:2] == (60, 40)
    assert metadata["exif_orientation"] == 6
    assert (metadata["encoded_width"], metadata["encoded_height"]) == (60, 40)


def test_calibrated_normal_bank_and_data_dependent_actions():
    mean, scale, metadata = load_bank()
    assert metadata["training_count"] == 40
    assert metadata["calibration_count"] == 12
    assert metadata["synthetic"] is True
    base = ROOT / "demo" / "samples"
    normal = cv2.imread(str(base / "normal.png"))
    defect = cv2.imread(str(base / "scratch.png"))
    blurred = cv2.imread(str(base / "blurred.png"))
    normal_result = analyze(normal, mean, scale, metadata)
    defect_result = analyze(defect, mean, scale, metadata)
    blurred_result = analyze(blurred, mean, scale, metadata)
    normal_agent = run_policy(normal, normal_result, mean, scale, synthetic_example=True)
    defect_agent = run_policy(defect, defect_result, mean, scale, synthetic_example=True)
    blur_agent = run_policy(blurred, blurred_result, mean, scale, synthetic_example=True)
    assert normal_result["score"] < normal_result["threshold"]
    assert normal_agent["decision"] == "PASS"
    assert defect_result["score"] > defect_result["threshold"]
    assert defect_agent["agent_trace"][1]["selected_tool"] == "inspect_crop"
    crop = defect_agent["crop_evidence"]
    assert crop["crop_width_native_pixels"] > 0 and crop["upscaled"] is False
    assert crop["crop_score_exceeds_pixel_threshold"] is True
    assert defect_agent["decision"] == "DEFECT_FOUND"
    assert "LOW_FOCUS" in blurred_result["quality"]["flags"]
    assert blur_agent["agent_trace"][1]["selected_tool"] == "request_new_capture"
    assert blur_agent["decision"] == "NEEDS_REVIEW"
    assert max(len(x["agent_trace"]) for x in (normal_agent, defect_agent, blur_agent)) <= 2


def test_native_crop_rejects_out_of_bounds_and_tiny_boxes():
    from app.agent.controller import inspect_crop
    mean, scale, metadata = load_bank()
    image = cv2.imread(str(ROOT / "demo" / "samples" / "scratch.png"))
    with pytest.raises(ValueError, match="INVALID_BBOX"):
        inspect_crop(image, [-1, 0, 20, 20], mean, scale, metadata["pixel_threshold"])
    with pytest.raises(ValueError, match="INVALID_BBOX"):
        inspect_crop(image, [2, 2, 7, 7], mean, scale, metadata["pixel_threshold"])


def test_region_mapping_stays_in_source_coordinates():
    mean, scale, metadata = load_bank()
    image = cv2.imread(str(ROOT / "demo" / "samples" / "scratch.png"))
    result = analyze(image, mean, scale, metadata)
    assert result["regions"]
    x1, y1, x2, y2 = result["regions"][0]["bbox_xyxy"]
    assert 0 <= x1 < x2 <= image.shape[1]
    assert 0 <= y1 < y2 <= image.shape[0]
    assert x2 - x1 > 20


def test_ecc_alignment_accepts_small_translation():
    image = cv2.imread(str(ROOT / "demo" / "samples" / "normal.png"))
    shifted = cv2.warpAffine(image, np.float32([[1, 0, 4], [0, 1, -3]]), (image.shape[1], image.shape[0]))
    aligned, evidence = align_affine(image, shifted)
    assert evidence["method"].startswith("cv2.findTransformECC") or evidence["method"] == "ecc_affine"
    assert evidence["accepted"] is True
    assert aligned is not None
    assert evidence["correlation"] > 0.72


def test_ecc_rejects_size_mismatch():
    a = np.zeros((30, 40, 3), np.uint8)
    b = np.zeros((31, 40, 3), np.uint8)
    aligned, evidence = align_affine(a, b)
    assert aligned is None
    assert evidence["reason"] == "SIZE_MISMATCH"


def test_local_retention_removes_old_records_and_assets():
    inspection_id = str(uuid4())
    payload = {"id": inspection_id, "created_at": "2000-01-01T00:00:00+00:00"}
    storage.save_inspection(inspection_id, payload)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    asset = ASSET_DIR / f"{inspection_id}_overlay.png"
    asset.write_bytes(b"test-artifact")
    assert storage.cleanup_expired(30) >= 1
    assert storage.get_inspection(inspection_id) is None
    assert not asset.exists()


def test_local_retention_removes_old_alignment_artifacts():
    artifact_id = str(uuid4())
    storage.register_artifact(artifact_id, "2000-01-01T00:00:00+00:00")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    assets = [ASSET_DIR / f"{artifact_id}_{suffix}.png" for suffix in ("aligned", "difference")]
    for asset in assets:
        asset.write_bytes(b"test-alignment-artifact")
    assert storage.cleanup_expired(30) >= 1
    assert all(not asset.exists() for asset in assets)


def test_benchmark_auc_and_average_precision_handle_tied_scores():
    labels = np.asarray([0, 0, 1, 1], dtype=np.uint8)
    scores = np.asarray([0.1, 0.2, 0.2, 0.9], dtype=np.float64)
    assert roc_auc(labels, scores) == pytest.approx(0.875)
    assert average_precision(labels, scores) == pytest.approx(5 / 6)


def test_pixel_metrics_include_normal_test_images_with_zero_masks():
    good_scores = np.zeros((2, 2), dtype=np.float32)
    defect_scores = np.asarray([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    good_mask = np.zeros((2, 2), dtype=np.uint8)
    defect_mask = np.asarray([[255, 0], [0, 0]], dtype=np.uint8)
    metrics = pixel_metrics([(good_mask, good_scores), (defect_mask, defect_scores)], 0.5)
    assert metrics["pixel_image_count"] == 2
    assert metrics["pixel_samples"] == 8
    assert metrics["pixel_auroc"] == pytest.approx(1.0)
    assert metrics["pixel_average_precision"] == pytest.approx(1.0)
    assert metrics["pixel_iou_at_frozen_normal_threshold"] == pytest.approx(1.0)


def test_visa_preparation_uses_official_split_and_binarizes_masks(tmp_path):
    dataset = tmp_path / "raw"
    normal_path = dataset / "candle" / "Data" / "Images" / "Normal" / "normal.JPG"
    anomaly_path = dataset / "candle" / "Data" / "Images" / "Anomaly" / "anomaly.JPG"
    mask_path = dataset / "candle" / "Data" / "Masks" / "Anomaly" / "anomaly.png"
    for path in (normal_path, anomaly_path, mask_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    normal = np.full((16, 20, 3), 120, dtype=np.uint8)
    anomaly = normal.copy(); anomaly[4:8, 6:10] = 255
    mask = np.zeros((16, 20), dtype=np.uint8); mask[4:8, 6:10] = 17
    assert cv2.imwrite(str(normal_path), normal)
    assert cv2.imwrite(str(anomaly_path), anomaly)
    assert cv2.imwrite(str(mask_path), mask)
    split_file = tmp_path / "1cls.csv"
    split_file.write_text(
        "object,split,label,image,mask\n"
        "candle,train,normal,candle/Data/Images/Normal/normal.JPG,\n"
        "candle,test,normal,candle/Data/Images/Normal/normal.JPG,\n"
        "candle,test,anomaly,candle/Data/Images/Anomaly/anomaly.JPG,candle/Data/Masks/Anomaly/anomaly.png\n",
        encoding="utf-8",
    )
    output = tmp_path / "prepared"
    manifest = prepare(dataset, split_file, output, "candle", None)
    assert manifest["counts"] == {"train_normal": 1, "test_normal": 1, "test_anomaly": 1}
    prepared_mask = cv2.imread(str(output / "candle" / "ground_truth" / "bad" / "anomaly_mask.png"), cv2.IMREAD_GRAYSCALE)
    assert set(np.unique(prepared_mask)) == {0, 255}
    assert (output / "candle" / "test" / "bad" / "anomaly.JPG").is_file()
    with pytest.raises(ValueError, match="Unsafe path"):
        resolve_dataset_file(dataset, "../outside.png")
