import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.patch_memory_v2 import (PatchConfig,PatchMemoryV2,valid_patch_centers,balanced_indices,
                                     patch_scores,restore_map,tile_boxes,choose_tile,random_tile)
from app.agent.patch_policy_v2 import run_v2_policy


def test_valid_centers_and_balanced_sampling_exclude_padding():
    valid=valid_patch_centers((32,32),(0,64,256,128))
    assert valid.sum()==512 and not valid[:8].any() and not valid[24:].any()
    a=balanced_indices((32,32),valid,96,np.random.default_rng(3))
    b=balanced_indices((32,32),valid,96,np.random.default_rng(3))
    assert np.array_equal(a,b) and len(np.unique(a))==96
    assert valid.ravel()[a].all()
    assert len(balanced_indices((32,32),valid,9999,np.random.default_rng(3)))==512


def test_spatial_sampling_covers_valid_strata():
    valid=np.ones((32,32),bool)
    ids=balanced_indices((32,32),valid,96,np.random.default_rng(3))
    y,x=np.unravel_index(ids,valid.shape)
    assert len(set((y//8*4+x//8).tolist()))==16


def test_scoring_pooling_does_not_treat_padding_as_evidence():
    small=np.ones((5,5),np.float32)
    valid=np.zeros((5,5),bool);valid[1:4,1:4]=True
    small[~valid]=999
    assert patch_scores(small,valid)==pytest.approx({"max":1,"top4":1,"region":1})
    small[2,2]=10
    scores=patch_scores(small,valid)
    assert scores["max"]==10 and scores["top4"]==pytest.approx(3.25)
    assert 1<scores["region"]<10
    with pytest.raises(ValueError):patch_scores(small,np.zeros_like(valid))


def test_tile_geometry_covers_all_corners_and_maps_to_native_pixels():
    image=np.zeros((800,1200,3),np.uint8)
    boxes=tile_boxes(image.shape)
    coverage=np.zeros(image.shape[:2],np.uint8)
    for x1,y1,x2,y2 in boxes:
        assert x2-x1==750 and y2-y1==500
        coverage[y1:y2,x1:x2]+=1
    assert coverage.min()>=1 and coverage.max()==4
    smap=np.zeros(image.shape[:2],np.float32);smap[600:,1000:]=5
    assert choose_tile(smap,boxes)==3
    assert random_tile(image,3)==random_tile(image.copy(),3)


def test_map_coordinates_survive_letterbox_and_sigma_change():
    raw=np.zeros((32,32),np.float32);raw[15,25]=10
    mapped=restore_map(raw,(0,64,256,128),(80,160),1.)
    y,x=np.unravel_index(mapped.argmax(),mapped.shape)
    assert 32<=y<=44 and 120<=x<=135


def _analysis(score=2.5):
    return {"category":"candle","score":score,"pass_threshold":2.,"threshold":3.,
            "quality":{"flags":[]},"regions":[{"bbox_xyxy":[1,2,20,30]}],"second_look":None}


def test_review_band_boundaries_and_inconclusive_detail_never_pass():
    image=np.zeros((128,128,3),np.uint8)
    assert run_v2_policy(image,_analysis(2.))["decision"]=="PASS"
    assert run_v2_policy(image,_analysis(3.))["decision"]=="NEEDS_REVIEW"
    a=_analysis();a["second_look"]={"source_bbox_xyxy":[0,0,80,80],"crop_score_exceeds_threshold":False,
                                     "evidence_id":"newmeasuredcrop","elapsed_ms":1.}
    result=run_v2_policy(image,a)
    assert result["decision"]=="NEEDS_REVIEW" and len(result["agent_trace"])==2
    assert result["agent_trace"][1]["selected_tool"]=="inspect_calibrated_detail"
    a["second_look"]["crop_score_exceeds_threshold"]=True
    assert run_v2_policy(image,a)["decision"]=="DEFECT_FOUND"
    a["second_look"]["crop_score_exceeds_threshold"]=False
    a["second_look"]["tool_error"]="DETAIL_INFERENCE_FAILED"
    assert run_v2_policy(image,a)["agent_trace"][-1]["decision_reason_code"]=="DETAIL_INFERENCE_FAILED"
    a["quality"]["flags"]=["LOW_FOCUS"]
    result=run_v2_policy(image,a)
    assert result["agent_status"]=="needs_input" and result["crop_evidence"] is None


def test_config_rejects_unfrozen_variants():
    for kwargs in ({"dimensions":7},{"scoring":"label_lookup"},{"pixel_quantile":1.}):
        with pytest.raises(ValueError):PatchConfig(**kwargs)


@pytest.mark.skipif(not os.getenv("REFLEX_ONNX_WEIGHTS"),reason="Requires actual verified weights")
def test_actual_features_match_v1_and_v2_roundtrip(tmp_path,monkeypatch):
    from app.core.patch_memory import PatchMemory
    weights=Path(os.environ["REFLEX_ONNX_WEIGHTS"])
    data=Path(os.environ["REFLEX_VISA_PREPARED"])
    paths=sorted((data/"candle/train/good").glob("*.JPG"))[:12]
    old=PatchMemory(weights);new=PatchMemoryV2(weights,PatchConfig(max_memory=32,patches_per_image=16))
    image=cv2.imread(str(paths[0]))
    first=old.embed(image)[0]
    monkeypatch.setenv("REFLEX_V2_FEATURE_CACHE",str(tmp_path/"cache"))
    assert np.array_equal(first,new.embed(image)[0])
    assert np.array_equal(first,new.embed(image)[0])
    new.fit(paths[:4],paths[4:8],tmp_path/"profile","candle")
    with pytest.raises(ValueError,match="disjoint"):new.calibrate_review(paths[4:8])
    new.calibrate_review(paths[8:])
    new.save(tmp_path/"profile")
    reloaded=PatchMemoryV2.load(tmp_path/"profile",weights)
    before,after=new.predict(image),reloaded.predict(image)
    assert before["score"]==after["score"] and np.array_equal(before["score_map"],after["score_map"])
    bank=tmp_path/"profile/patch_bank.npz";bank.write_bytes(bank.read_bytes()+b"tamper")
    with pytest.raises(RuntimeError,match="SHA256"):PatchMemoryV2.load(tmp_path/"profile",weights)


@pytest.mark.skipif(not os.getenv("REFLEX_ONNX_WEIGHTS"),reason="Requires actual verified weights")
def test_v2_api_runs_separately_calibrated_detail_and_exports_evidence(client,tmp_path,monkeypatch):
    import app.main as service
    from app.core.patch_memory_v2 import fit_detail
    from app.core.engine import _patch_profile
    from collections import defaultdict,deque
    weights=Path(os.environ["REFLEX_ONNX_WEIGHTS"])
    data=Path(os.environ["REFLEX_VISA_PREPARED"])
    paths=sorted((data/"candle/train/good").glob("*.JPG"))[:12]
    directory=tmp_path/"v2"
    model=PatchMemoryV2(weights,PatchConfig(max_memory=32,patches_per_image=16))
    model.fit(paths[:4],paths[4:8],directory,"candle")
    detail=fit_detail(paths[:4],paths[4:8],model,directory/"detail")
    image=cv2.imread(str(paths[8]))
    score=model.predict(image)["score"]
    # Force review branch in an integration fixture; never benchmark with these bounds.
    model.metadata.update(pass_threshold=score-.01,image_threshold=score+.01,detail_directory="detail")
    model.save(directory)
    monkeypatch.setattr(service,"MODEL_DIR",directory)
    monkeypatch.setattr(service,"_UPLOADS_BY_CLIENT",defaultdict(deque))
    monkeypatch.delenv("REFLEX_PROFILES_DIR",raising=False)
    monkeypatch.delenv("REFLEX_V2_FEATURE_CACHE",raising=False)
    _patch_profile.cache_clear()
    response=client.post("/api/inspections",data={"category":"candle"},files={"file":("source.jpg",paths[8].read_bytes(),"image/jpeg")})
    assert response.status_code==200,response.text
    value=response.json()
    assert value["model_version"]=="reflex-resnet50-patch-memory-2"
    assert value["score_type"]=="local_normal_patch_support_l2"
    assert value["pass_threshold"]==pytest.approx(score-.01,abs=1e-6)
    assert len(value["agent_trace"])==2 and value["agent_trace"][1]["selected_tool"]=="inspect_calibrated_detail"
    crop=value["crop_evidence"]
    assert crop["normal_bank_sha256"]==detail.metadata["normal_bank_sha256"]
    assert crop["additional_camera_view"] is False
    assert value["decision"] in ("DEFECT_FOUND","NEEDS_REVIEW")
    assert client.get(value["assets"]["roi_url"]).status_code==200
    exported=client.get(f"/api/inspections/{value['id']}/export?format=json")
    assert "pass_threshold" in exported.text and "inspect_calibrated_detail" in exported.text
