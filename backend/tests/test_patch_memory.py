import numpy as np
import pytest
import os
from pathlib import Path

from app.core.patch_memory import preprocess, unletterbox, nearest_distances, coreset, PatchMemory


def test_preprocess_rgb_normalization_and_border_preservation():
    image = np.zeros((80, 160, 3), np.uint8)
    image[:, :, 2] = 255
    blob, box = preprocess(image)
    assert blob.shape == (1, 3, 256, 256)
    assert box == (0, 64, 256, 128)
    assert blob[0, 0, 128, 128] == pytest.approx((1-.485)/.229)
    assert blob[0, 2, 128, 128] == pytest.approx(-.406/.225)
    assert np.array_equal(blob[:, :, 0], blob[:, :, 64])
    with pytest.raises(ValueError):
        preprocess(np.zeros((10, 10), np.uint8))


def test_unletterbox_preserves_source_coordinates():
    score = np.zeros((256, 256), np.float32)
    score[110:145, 190:220] = 10
    restored = unletterbox(score, (0,64,256,128), (80,160))
    y, x = np.unravel_index(np.argmax(restored), restored.shape)
    assert 29 <= y <= 51 and 119 <= x <= 138
    assert restored.shape == (80,160)
    assert restored[0,0] < .001


def test_exact_nearest_neighbor_distance_is_position_independent():
    memory = np.array([[1,2],[4,6]],np.float32)
    query = np.array([[4,6],[1,2],[1,6]],np.float32)
    assert nearest_distances(query,memory) == pytest.approx([0,0,3])
    with pytest.raises(ValueError):
        nearest_distances(query,np.empty((0,2),np.float32))


def test_coreset_is_deterministic_unique_and_from_normal_pool():
    features = np.random.default_rng(1).normal(size=(100,16)).astype(np.float32)
    first = coreset(features,20,np.random.default_rng(3))
    second = coreset(features,20,np.random.default_rng(3))
    assert np.array_equal(first,second)
    assert len(np.unique(first,axis=0)) == 20
    assert all(any(np.array_equal(row,original) for original in features) for row in first)


def test_fit_rejects_calibration_leakage_before_feature_extraction(tmp_path):
    paths = []
    for i in range(4):
        p = tmp_path/f"{i}.png"
        p.write_bytes(bytes([i]))
        paths.append(p)
    instance = PatchMemory.__new__(PatchMemory)
    with pytest.raises(ValueError,match="disjoint"):
        instance.fit(paths,paths,tmp_path/"out","candle")


def test_invalid_pretrained_weights_are_never_used(tmp_path):
    p = tmp_path/"fake.onnx"
    p.write_bytes(b"not a model")
    with pytest.raises(RuntimeError,match="SHA256"):
        PatchMemory(p)


@pytest.mark.skipif(not os.getenv("REFLEX_ONNX_WEIGHTS"),reason="Set REFLEX_ONNX_WEIGHTS for real pretrained integration check")
def test_real_pretrained_fit_reload_and_bank_tamper(tmp_path):
    import cv2
    from app.core.patch_memory import FEATURE_LAYERS
    weights=Path(os.environ["REFLEX_ONNX_WEIGHTS"])
    root=Path(os.environ["REFLEX_VISA_PREPARED"])
    paths=sorted((root/"candle"/"train"/"good").glob("*.JPG"))[:8]
    assert len(paths)==8
    model=PatchMemory(weights)
    features,grid,box=model.embed(cv2.imread(str(paths[0])))
    assert features.shape==(1024,1536) and grid==(32,32)
    assert np.isfinite(features).all() and np.any(features>0)
    assert model.layers==FEATURE_LAYERS
    model.fit(paths[:4],paths[4:],tmp_path/"model","candle",max_memory=32,patches_per_image=16)
    image=cv2.imread(str(paths[0]))
    before=model.analyze(image)
    loaded=PatchMemory.load(tmp_path/"model",weights)
    after=loaded.analyze(image)
    assert before["score"]==pytest.approx(after["score"],rel=1e-7)
    assert np.array_equal(before["score_map"],after["score_map"])
    assert before["score_map"].shape==image.shape[:2]
    assert before["category"]=="candle"
    bank=tmp_path/"model"/"patch_bank.npz"
    bank.write_bytes(bank.read_bytes()+b"tampered")
    with pytest.raises(RuntimeError,match="SHA256"):
        PatchMemory.load(tmp_path/"model",weights)
