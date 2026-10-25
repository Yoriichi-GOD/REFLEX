from pathlib import Path
import json

import cv2

ROOT = Path(__file__).resolve().parents[2]


def image_bytes(name: str) -> bytes:
    return (ROOT / "demo" / "samples" / f"{name}.png").read_bytes()


def test_health_and_supported_profile(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["opencv_version"].startswith("5.")
    assert health.json()["model_ready"] is True
    ready = client.get("/api/ready")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"
    assert health.headers["content-security-policy"].startswith("default-src 'self'")
    profile = client.get("/api/profiles").json()["profiles"][0]
    assert profile["category"] == "synthetic_machined_plate"
    assert profile["synthetic"] is True


def test_new_upload_runs_cv_and_persists_real_artifacts(client):
    response = client.post("/api/inspections", files={"file": ("../../scratch.png", image_bytes("scratch"), "image/png")})
    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "DEFECT_FOUND"
    assert result["cv_version"].startswith("5.")
    assert result["image_sha256"]
    assert result["synthetic"] is True
    assert result["agent_trace"][1]["selected_tool"] == "inspect_crop"
    assert result["crop_evidence"]["upscaled"] is False
    for key in ("original_url", "heatmap_url", "overlay_url", "mask_url", "roi_url"):
        artifact = client.get(result["assets"][key])
        assert artifact.status_code == 200
        assert artifact.headers["content-type"].startswith("image/png")
    stored = client.get(f"/api/inspections/{result['id']}").json()
    assert stored["id"] == result["id"]
    assert stored["agent_trace"][1]["tool_result_id"] == result["agent_trace"][1]["tool_result_id"]
    exported = client.get(f"/api/inspections/{result['id']}/export?format=json")
    assert exported.status_code == 200 and result["image_sha256"] in exported.text
    assert client.get(f"/api/inspections/{result['id']}/export?format=html").status_code == 200


def test_inspection_logs_are_correlatable_without_logging_source_hash(client, caplog):
    caplog.set_level("INFO", logger="reflex.inspection")
    caplog.set_level("INFO", logger="reflex.request")
    response = client.post("/api/inspections", files={"file": ("scratch.png", image_bytes("scratch"), "image/png")})
    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    inspection_id = response.json()["id"]
    events = [json.loads(record.message) for record in caplog.records if record.name == "reflex.inspection"]
    event = next(item for item in events if item["inspection_id"] == inspection_id)
    assert event["request_id"] == request_id
    assert event["opencv_version"].startswith("5.")
    assert event["agent_tools"][-1] == "inspect_crop"
    assert "source_sha256" not in event
    request_events = [json.loads(record.message) for record in caplog.records if record.name == "reflex.request"]
    request_event = next(item for item in request_events if item["request_id"] == request_id)
    assert request_event["route"] == "/api/inspections"
    assert request_event["status_code"] == 200


def test_low_quality_requests_an_actual_new_capture(client):
    response = client.post("/api/inspections", files={"file": ("soft.png", image_bytes("blurred"), "image/png")})
    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "NEEDS_REVIEW"
    assert result["needs_action"]["type"] == "new_capture"
    assert result["agent_trace"][-1]["selected_tool"] == "request_new_capture"
    next_response = client.post(f"/api/inspections/{result['id']}/continue", files={"file": ("view.png", image_bytes("normal"), "image/png")})
    assert next_response.status_code == 200
    child = next_response.json()
    assert child["previous_inspection_id"] == result["id"]
    assert len(child["agent_trace"]) > len(result["agent_trace"])


def test_review_is_separate_and_survives_fetch(client):
    created = client.post("/api/inspections", files={"file": ("normal.png", image_bytes("normal"), "image/png")}).json()
    saved = client.post(f"/api/inspections/{created['id']}/review", json={"decision": "override_acceptable", "note": "Operator inspected the part."})
    assert saved.status_code == 200
    assert saved.json()["model_decision_unchanged"] is True
    refreshed = client.get(f"/api/inspections/{created['id']}").json()
    assert refreshed["decision"] == created["decision"] == "PASS"
    assert refreshed["reviewer"]["decision"] == "override_acceptable"
    assert refreshed["reviews"][0]["note"] == "Operator inspected the part."


def test_invalid_and_cross_inspection_requests_fail_safely(client):
    invalid = client.post("/api/inspections", files={"file": ("wrong.png", b"not an image", "image/png")})
    assert invalid.status_code == 400
    missing = client.get("/api/inspections/not-a-real-id")
    assert missing.status_code == 404
    denied = client.post("/api/inspections/not-a-real-id/continue", files={"file": ("normal.png", image_bytes("normal"), "image/png")})
    assert denied.status_code == 404
    mismatch = client.post("/api/inspections", files={"file": ("image.jpg", image_bytes("normal"), "image/jpeg")})
    assert mismatch.status_code == 415


def test_alignment_route_returns_structured_output(client):
    image = image_bytes("normal")
    shifted_array = cv2.imdecode(__import__("numpy").frombuffer(image, dtype=__import__("numpy").uint8), cv2.IMREAD_COLOR)
    import numpy as np
    shifted = cv2.warpAffine(shifted_array, np.float32([[1, 0, 3], [0, 1, 2]]), (shifted_array.shape[1], shifted_array.shape[0]))
    ok, encoded = cv2.imencode(".png", shifted)
    assert ok
    result = client.post("/api/align", files={"reference": ("reference.png", image, "image/png"), "candidate": ("candidate.png", encoded.tobytes(), "image/png")})
    assert result.status_code == 200
    assert result.json()["accepted"] is True
    assert result.json()["comparison"]["pixel_count"] > 0
    assert client.get(result.json()["difference_url"]).status_code == 200
