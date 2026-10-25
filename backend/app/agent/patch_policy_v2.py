"""Bounded v2 disposition policy; an abstention is not a correct detection."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import uuid


def run_v2_policy(image,analysis,synthetic_example=False):
    evidence=hashlib.sha256(image.tobytes()).hexdigest()[:16]
    trace=[{"step":1,"state_before":"INGESTED","selected_tool":"inspect_full",
            "tool_input":{"image_sha256_prefix":evidence,"category":analysis["category"]},
            "tool_result_id":evidence,"observation":{"anomaly_score":analysis["score"],
            "threshold":analysis["threshold"],"pass_threshold":analysis["pass_threshold"],
            "quality_flags":analysis["quality"]["flags"]},"decision_reason_code":"V2_NORMAL_PATCH_EVIDENCE",
            "state_after":"OBSERVED","elapsed_ms":0,"created_at":datetime.now(timezone.utc).isoformat(),
            "synthetic_example":synthetic_example}]
    second=analysis.get("second_look")
    crop=None
    if analysis["quality"]["flags"]:
        decision,status,reason="NEEDS_REVIEW","needs_input","IMAGE_QUALITY_INSUFFICIENT"
        action={"type":"new_capture","guidance":"Retake the whole part in focus with even lighting and no obstruction."}
    elif analysis["score"]>analysis["threshold"]:
        decision="DEFECT_FOUND" if analysis["regions"] else "NEEDS_REVIEW"
        status="complete" if decision=="DEFECT_FOUND" else "needs_review"
        reason="LOCALIZED_SCORE_ABOVE_NORMAL_THRESHOLD" if decision=="DEFECT_FOUND" else "UNLOCALIZED_ANOMALY_EVIDENCE"
        action=None if decision=="DEFECT_FOUND" else {"type":"human_review","guidance":"Review the full image; no stable region was localized."}
    elif analysis["score"]<=analysis["pass_threshold"]:
        decision,status,reason,action="PASS","complete","BELOW_NORMAL_CALIBRATED_PASS_BOUND",None
    elif second is not None:
        crop=second
        decision="DEFECT_FOUND" if second["crop_score_exceeds_threshold"] else "NEEDS_REVIEW"
        status="complete" if decision=="DEFECT_FOUND" else "needs_review"
        reason="CALIBRATED_DETAIL_ALERT" if decision=="DEFECT_FOUND" else (second.get("tool_error") or "SECOND_LOOK_INCONCLUSIVE")
        action=None if decision=="DEFECT_FOUND" else {"type":"human_review","guidance":"Second inspection remained inconclusive; review the source detail."}
        trace.append({"step":2,"state_before":"UNCERTAIN","selected_tool":"inspect_calibrated_detail",
                      "tool_input":{"bbox_xyxy":second["source_bbox_xyxy"],"mode":"native_source_detail_separate_normal_bank"},
                      "tool_result_id":second["evidence_id"],"tool_result":second,"decision_reason_code":reason,
                      "state_after":decision,"elapsed_ms":second["elapsed_ms"],
                      "created_at":datetime.now(timezone.utc).isoformat(),"synthetic_example":synthetic_example})
    else:
        decision,status,reason="NEEDS_REVIEW","needs_review","BETWEEN_PASS_AND_DEFECT_BOUNDARIES"
        action={"type":"human_review","guidance":"The score lies in the review band; calibrated detail evidence is unavailable."}
    if action is not None and len(trace)==1:
        trace.append({"step":2,"state_before":"OBSERVED","selected_tool":"request_new_capture" if status=="needs_input" else "request_human_review",
                      "tool_input":{"reason":reason},"tool_result_id":str(uuid.uuid4()),"tool_result":{"requested":True},
                      "decision_reason_code":reason,"state_after":status.upper(),"elapsed_ms":0,
                      "created_at":datetime.now(timezone.utc).isoformat(),"synthetic_example":synthetic_example})
    return {"decision":decision,"decision_text":{"PASS":"No modeled visual anomaly detected below the calibrated pass boundary. Not a safety certification.",
             "DEFECT_FOUND":"Localized visual anomaly detected. Confirm before rejecting the item.",
             "NEEDS_REVIEW":"Evidence is unresolved; review or another capture is required."}[decision],
            "agent_status":status,"needs_action":action,"agent_trace":trace,"crop_evidence":crop}
