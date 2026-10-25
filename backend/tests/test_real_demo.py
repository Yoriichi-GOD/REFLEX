from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_real_catalog_preserves_original_bytes_and_omits_ground_truth():
    manifest = json.loads((ROOT / "demo" / "real" / "cases.json").read_text())
    assert len(manifest["cases"]) == 6
    assert {c["category"] for c in manifest["cases"]} == {"candle", "cashew"}
    assert not list((ROOT / "demo" / "real").glob("*.png"))
    for case in manifest["cases"]:
        assert not {"label", "mask", "expected_decision", "prediction", "score"}.intersection(case)
        image = ROOT / case["image_url"].lstrip("/")
        assert hashlib.sha256(image.read_bytes()).hexdigest() == case["sha256"]
        assert case["synthetic"] is False and case["attribution"]["license"] == "CC BY 4.0"
        assert cv2.imread(str(image)) is not None


def configure(monkeypatch):
    import app.main as service
    monkeypatch.setenv("REFLEX_PROFILES_DIR", str(ROOT / "demo" / "profiles"))
    monkeypatch.setenv("REFLEX_DEFAULT_PROFILE", "candle")
    monkeypatch.setenv("REFLEX_EVALUATION_DIR", str(ROOT / "demo" / "evaluations"))
    monkeypatch.setenv("REFLEX_ONNX_WEIGHTS", str(ROOT / "demo" / "pretrained" / "resnet50-v1-12.onnx"))
    monkeypatch.setattr(service, "_UPLOADS_BY_CLIENT", defaultdict(deque))


def test_both_real_profiles_run_live_without_mutating_global_category(client, monkeypatch):
    configure(monkeypatch)
    profiles = client.get("/api/profiles").json()["profiles"]
    assert {p["category"] for p in profiles} == {"candle", "cashew", "synthetic_machined_plate"}
    assert [p["category"] for p in profiles if p["default"]] == ["candle"]
    bank_hashes = {}
    for category in ("candle", "cashew", "candle"):
        cases = client.get("/api/demo-cases", params={"category": category}).json()["cases"]
        assert len(cases) == 3 and all(c["category"] == category for c in cases)
        case = cases[1]
        original = client.get(case["image_url"])
        assert original.status_code == 200 and hashlib.sha256(original.content).hexdigest() == case["sha256"]
        response = client.post("/api/inspections", data={"category": category}, files={"file": (case["id"] + ".jpg", original.content, "image/jpeg")})
        assert response.status_code == 200
        result = response.json()
        assert result["class_name"] == category and result["synthetic"] is False
        assert result["model_mode"] == "opencv_dnn_patch_memory"
        assert result["data_source"] == "VisA real benchmark photograph"
        assert result["demo_attribution"]["dataset"] == "VisA"
        assert result["agent_trace"][0]["tool_input"]["category"] == category
        metadata = json.loads((ROOT / "demo" / "profiles" / category / "metadata.json").read_text())
        assert result["threshold"] == pytest.approx(metadata["image_threshold"], abs=1e-6)
        if category in bank_hashes:
            assert result["normal_bank_sha256"] == bank_hashes[category]
        bank_hashes[category] = result["normal_bank_sha256"]
        for key in ("original_url", "heatmap_url", "overlay_url"):
            assert client.get(result["assets"][key]).status_code == 200
        evaluation = client.get("/api/evaluations/latest", params={"category": category}).json()
        assert evaluation["synthetic"] is False and category in evaluation["dataset"]
    assert bank_hashes["candle"] != bank_hashes["cashew"]
    assert client.get("/api/demo-cases", params={"category": "../../other"}).status_code == 422
    # Legacy examples remain explicitly synthetic and use their original profile.
    assert client.get("/api/demo-cases", params={"category": "synthetic_machined_plate"}).json()["cases"]


def test_compare_view_has_separate_original_heatmap_and_overlay_sources(client):
    page = client.get("/").text
    script = client.get("/app.js").text
    assert 'data-layer="compare"' in page
    assert "Original photograph" in script and "Anomaly heatmap" in script and "Model overlay" in script
    assert "original_url" in script and "heatmap_url" in script and "overlay_url" in script
    assert 'id="demo-credit"' in page
