import os
from pathlib import Path
from collections import defaultdict, deque

import numpy as np
import pytest

from app.agent.controller import run_policy


def analysis():
    return {"model_mode":"opencv_dnn_patch_memory","category":"candle","quality":{"flags":[]},
            "score":4.,"threshold":3.,"regions":[{"bbox_xyxy":[10,10,40,40]}]}


def test_patch_policy_does_not_treat_rescaled_crop_as_independent_confirmation():
    result=run_policy(np.zeros((128,128,3),np.uint8),analysis(),None,None)
    assert result["decision"]=="DEFECT_FOUND"
    assert [s["selected_tool"] for s in result["agent_trace"]]==["inspect_full"]
    assert result["agent_trace"][0]["tool_input"]["category"]=="candle"


def test_patch_policy_abstains_on_quality_or_unlocalized_evidence():
    source=np.zeros((128,128,3),np.uint8)
    low=analysis();low["quality"]["flags"]=["LOW_FOCUS"];low["score"]=0
    result=run_policy(source,low,None,None)
    assert result["decision"]=="NEEDS_REVIEW" and result["needs_action"]["type"]=="new_capture"
    unlocalized=analysis();unlocalized["regions"]=[]
    result=run_policy(source,unlocalized,None,None)
    assert result["decision"]=="NEEDS_REVIEW" and result["needs_action"]["type"]=="human_review"
    normal=analysis();normal["score"]=1
    assert run_policy(source,normal,None,None)["decision"]=="PASS"


@pytest.mark.skipif(not os.getenv("REFLEX_ONNX_WEIGHTS"),reason="Requires verified real pretrained profile")
def test_real_patch_profile_api_matches_detector_and_rejects_wrong_category(client,monkeypatch):
    import app.main as service
    monkeypatch.setattr(service,"_UPLOADS_BY_CLIENT",defaultdict(deque))
    from app.core.engine import load_bank,analyze
    from app.core.model import read_bgr
    root=Path(__file__).resolve().parents[2]
    directory=root/"reports"/"improvement_20261024"/"models"/"candle"
    monkeypatch.setattr(service,"MODEL_DIR",directory)
    profile=client.get("/api/profiles").json()["profiles"][0]
    assert profile["display_name"]=="VisA · candle" and not profile["synthetic"]
    assert client.get("/api/ready").status_code==200
    evaluation=client.get("/api/evaluations/latest").json()
    if evaluation.get("status")!="not_evaluated":
        assert evaluation["dataset"]=="VisA · candle" and evaluation["synthetic"] is False
    path=next((Path(os.environ["REFLEX_VISA_PREPARED"])/"candle"/"train"/"good").glob("*.JPG"))
    mean,scale,meta=load_bank(directory)
    expected=analyze(read_bgr(path),mean,scale,meta)
    response=client.post("/api/inspections",data={"category":"candle"},files={"file":(path.name,path.read_bytes(),"image/jpeg")})
    assert response.status_code==200
    result=response.json()
    assert result["score"]==pytest.approx(expected["score"],abs=1e-6)
    assert result["model_mode"]=="opencv_dnn_patch_memory" and result["score_type"]=="nearest_normal_patch_l2"
    assert all(s["selected_tool"]!="inspect_crop" for s in result["agent_trace"])
    assert client.get(result["assets"]["overlay_url"]).status_code==200
    wrong=client.post("/api/inspections",data={"category":"cashew"},files={"file":(path.name,path.read_bytes(),"image/jpeg")})
    assert wrong.status_code==422 and wrong.json()["detail"]["code"]=="CATEGORY_UNSUPPORTED"
