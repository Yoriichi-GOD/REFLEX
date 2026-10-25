from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import time
import uuid

import cv2
import numpy as np

from app.core.model import _score_features, feature_map


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_id(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]


def inspect_crop(image: np.ndarray, bbox: list[int], mean: np.ndarray, scale: np.ndarray, pixel_threshold: float) -> dict:
    width, height = image.shape[1], image.shape[0]
    if len(bbox) != 4:
        raise ValueError("INVALID_BBOX")
    x1, y1, x2, y2 = (int(v) for v in bbox)
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height or x2 - x1 < 8 or y2 - y1 < 8:
        raise ValueError("INVALID_BBOX")
    crop = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 150)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    native_map = _score_features(feature_map(crop), mean, scale)
    crop_score = float(np.quantile(native_map, 0.995))
    return {
        "evidence_id": _evidence_id(crop.tobytes()),
        "source_bbox_xyxy": [x1, y1, x2, y2],
        "crop_width_native_pixels": int(crop.shape[1]),
        "crop_height_native_pixels": int(crop.shape[0]),
        "upscaled": False,
        "crop_anomaly_score": crop_score,
        "calibrated_pixel_threshold": float(pixel_threshold),
        "crop_score_exceeds_pixel_threshold": bool(crop_score > pixel_threshold),
        "edge_density": float(np.mean(edges > 0)),
        "laplacian_variance": float(lap.var()),
        "gray_p10_p90_range": float(np.percentile(gray, 90) - np.percentile(gray, 10)),
        "analysis_note": "OpenCV 5 re-ran the normal-bank feature comparison and edge/texture measurements on source pixels in this crop.",
    }


def run_policy(image: np.ndarray, analysis: dict, mean: np.ndarray, scale: np.ndarray, synthetic_example: bool = False) -> dict:
    if analysis.get("model_version") == "reflex-resnet50-patch-memory-2":
        from app.agent.patch_policy_v2 import run_v2_policy
        return run_v2_policy(image,analysis,synthetic_example)
    if analysis.get("model_mode") == "opencv_dnn_patch_memory":
        return run_patch_policy(image, analysis, synthetic_example)
    trace = []
    inspection_id = str(uuid.uuid4())
    initial_id = _evidence_id(image.tobytes())
    trace.append({
        "step": 1, "state_before": "INGESTED", "observation": {
            "quality_flags": analysis["quality"]["flags"], "anomaly_score": analysis["score"],
            "threshold": analysis["threshold"], "candidate_bbox_xyxy": analysis["regions"][0]["bbox_xyxy"] if analysis["regions"] else None,
        },
        "selected_tool": "inspect_full", "tool_input": {"image_sha256_prefix": initial_id, "category": analysis.get("category", "synthetic_machined_plate")},
        "tool_result_id": initial_id, "decision_reason_code": "INITIAL_OPENCV5_INSPECTION",
        "state_after": "OBSERVED", "elapsed_ms": 0, "created_at": _now(), "synthetic_example": synthetic_example,
    })
    flags = analysis["quality"]["flags"]
    if flags:
        guidance = "Retake the image in focus with the whole part visible and even lighting. REFLEX will not issue an automatic pass from this capture."
        trace.append({
            "step": 2, "state_before": "OBSERVED", "observation": {"quality_flags": flags},
            "selected_tool": "request_new_capture", "tool_input": {"reason_codes": flags, "capture_guidance": guidance},
            "tool_result_id": str(uuid.uuid4()), "tool_result": {"requested": True, "new_image_received": False},
            "decision_reason_code": "IMAGE_QUALITY_INSUFFICIENT", "state_after": "NEEDS_INPUT",
            "elapsed_ms": 0, "created_at": _now(), "synthetic_example": synthetic_example,
        })
        return {"decision": "NEEDS_REVIEW", "decision_text": "Image or evidence is insufficient for automated disposition; please review or capture another view.", "needs_action": {"type": "new_capture", "guidance": guidance}, "agent_trace": trace, "agent_status": "needs_input"}
    if analysis["score"] <= analysis["threshold"]:
        return {"decision": "PASS", "decision_text": "No modeled visual anomaly detected in the inspected region. Not a safety certification.", "needs_action": None, "agent_trace": trace, "agent_status": "complete"}
    if not analysis["regions"]:
        guidance = "The score crossed its normal calibration threshold, but no stable region was localized. Ask an operator to review the full image or capture another view."
        trace.append({
            "step": 2, "state_before": "OBSERVED", "observation": {"anomaly_score": analysis["score"], "localized_regions": 0},
            "selected_tool": "request_human_review", "tool_input": {"reason": "SCORE_ABOVE_THRESHOLD_WITHOUT_LOCALIZATION"},
            "tool_result_id": str(uuid.uuid4()), "tool_result": {"requested": True},
            "decision_reason_code": "UNLOCALIZED_ANOMALY_EVIDENCE", "state_after": "NEEDS_REVIEW",
            "elapsed_ms": 0, "created_at": _now(), "synthetic_example": synthetic_example,
        })
        return {"decision": "NEEDS_REVIEW", "decision_text": "Image or evidence is insufficient for automated disposition; please review or capture another view.", "needs_action": {"type": "human_review", "guidance": guidance}, "agent_trace": trace, "agent_status": "needs_review"}
    region = analysis["regions"][0]
    started = time.perf_counter()
    crop_evidence = inspect_crop(image, region["bbox_xyxy"], mean, scale, analysis["pixel_threshold"])
    elapsed = (time.perf_counter() - started) * 1000
    trace.append({
        "step": 2, "state_before": "ANOMALY_LOCALIZED", "observation": {
            "anomaly_score": analysis["score"], "threshold": analysis["threshold"], "bbox_xyxy": region["bbox_xyxy"],
        },
        "selected_tool": "inspect_crop", "tool_input": {"bbox_xyxy": region["bbox_xyxy"], "mode": "native_source_pixels"},
        "tool_result_id": crop_evidence["evidence_id"], "tool_result": crop_evidence,
        "decision_reason_code": "LOCALIZED_SCORE_ABOVE_NORMAL_THRESHOLD", "state_after": "EVIDENCE_UPDATED",
        "elapsed_ms": round(elapsed, 3), "created_at": _now(), "synthetic_example": synthetic_example,
    })
    if crop_evidence["crop_score_exceeds_pixel_threshold"]:
        decision = "DEFECT_FOUND"
        text = "Localized visual anomaly detected. Confirm before rejecting the item."
        guidance = None
    else:
        decision = "NEEDS_REVIEW"
        text = "The second look did not corroborate the localized score; human review is required."
        guidance = {"type": "human_review", "guidance": "Review the highlighted native-resolution crop; the second-pass evidence was inconclusive."}
    trace[-1]["decision_reason_code"] = "CROP_CORROBORATED" if decision == "DEFECT_FOUND" else "CROP_DID_NOT_CORROBORATE"
    trace[-1]["state_after"] = decision
    return {"decision": decision, "decision_text": text, "needs_action": guidance, "agent_trace": trace, "agent_status": "complete" if decision != "NEEDS_REVIEW" else "needs_review", "crop_evidence": crop_evidence}


def run_patch_policy(image: np.ndarray, analysis: dict, synthetic_example: bool = False) -> dict:
    """Patch evidence is calibrated at full-image scale; arbitrary crops are not.

    Do not turn a resized crop into a purported independent confirmation.
    Quality gating and human review remain available; no second-look gain claimed.
    """
    evidence=_evidence_id(image.tobytes())
    flags=analysis["quality"]["flags"]
    trace=[{"step":1,"state_before":"INGESTED","selected_tool":"inspect_full",
            "tool_input":{"image_sha256_prefix":evidence,"category":analysis["category"]},
            "tool_result_id":evidence,"observation":{"anomaly_score":analysis["score"],"threshold":analysis["threshold"],"quality_flags":flags},
            "decision_reason_code":"PRETRAINED_NORMAL_PATCH_COMPARISON","state_after":"OBSERVED",
            "elapsed_ms":0,"created_at":_now(),"synthetic_example":synthetic_example}]
    if flags:
        action={"type":"new_capture","guidance":"Retake the whole part in focus with even lighting."}
        decision,status,tool,reason="NEEDS_REVIEW","needs_input","request_new_capture","IMAGE_QUALITY_INSUFFICIENT"
    elif analysis["score"]<=analysis["threshold"]:
        return {"decision":"PASS","decision_text":"No modeled visual anomaly detected. Not a safety certification.","needs_action":None,"agent_trace":trace,"agent_status":"complete"}
    elif not analysis["regions"]:
        action={"type":"human_review","guidance":"Anomaly score exceeded normal calibration without stable localization; review the full image."}
        decision,status,tool,reason="NEEDS_REVIEW","needs_review","request_human_review","UNLOCALIZED_ANOMALY_EVIDENCE"
    else:
        return {"decision":"DEFECT_FOUND","decision_text":"Localized visual anomaly detected. Confirm before rejecting the item.","needs_action":None,"agent_trace":trace,"agent_status":"complete"}
    trace.append({"step":2,"state_before":"OBSERVED","selected_tool":tool,"tool_input":{"reason":reason},
                  "tool_result_id":str(uuid.uuid4()),"tool_result":{"requested":True},"decision_reason_code":reason,
                  "state_after":status.upper(),"elapsed_ms":0,"created_at":_now(),"synthetic_example":synthetic_example})
    return {"decision":decision,"decision_text":"Image or evidence is insufficient for automated disposition; please review or capture another view.",
            "needs_action":action,"agent_trace":trace,"agent_status":status}
