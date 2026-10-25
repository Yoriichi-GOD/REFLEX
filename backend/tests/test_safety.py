"""Evidence-dependent safety/compatibility checks, separate from physical validation."""
import copy,hashlib,json,time
from pathlib import Path
import cv2,numpy as np,pytest
from fastapi.testclient import TestClient
from reflex_safety.recipe import load_recipe,Recipe,validate_quad
from reflex_safety.engine import RecipeEngine,analyze_video
from reflex_safety.vision import analyze_frame

def observation(index,t,classes=None,usable=True):
    recipe=load_recipe();classes=classes or {}
    return {'frame_index':index,'source_timestamp_ms':t,'frame_sha256':hashlib.sha256(str(index).encode()).hexdigest(),'evidence_id':f'e{index}','quality':{'usable':usable,'flags':[] if usable else ['OCCLUDED']},'observations':[{'slot_id':k,'class_id':classes.get(k,'missing'),'confidence':.9,'image_quality':1,'quality_flags':[],'expected_classes':recipe.parts[v.requires].classes,'bbox_xyxy':[0,0,20,20],'status':'missing'} for k,v in recipe.slots.items()]}
def stable(engine,classes,start=0,t=0):
    for i in range(3):engine.feed(observation(start+i,t+200*i,classes))
def test_recipe_cycle_and_unknown_slot_rejected():
    data=load_recipe().model_dump();data['steps'][0]['requires']=['fit_fasteners']
    with pytest.raises(ValueError,match='cycle'):Recipe.model_validate(data)
    data=load_recipe().model_dump();data['steps'][0]['slots']=['fake']
    with pytest.raises(ValueError,match='slot'):Recipe.model_validate(data)
def test_bad_quad_and_mirror_rejected():
    for q in [[[0,0],[0,1],[1,1],[1,0]],[[0,0],[1,1],[1,0],[0,1]],[[0,0],[.1,0],[.1,.1],[0,.1]]]:
        with pytest.raises(ValueError):validate_quad(q)
def test_ordered_recipe_pass_requires_unique_temporally_separated_evidence():
    e=RecipeEngine(load_recipe(),'empty_observed');stable(e,{})
    slots={'spacer_left':'short_spacer','spacer_right':'short_spacer'};stable(e,slots,3,600)
    slots['cover']='cover_plate';stable(e,slots,6,1200)
    slots.update(left_fastener='fastener',right_fastener='fastener');stable(e,slots,9,1800)
    assert e.snapshot(True)['decision']['status']=='PASS'
    before=len(e.observations);assert e.feed(observation(11,2400,slots)) is False
    assert len(e.observations)==before
    assert e.snapshot()['decision']['status']=='HOLD_FOR_REVIEW'
def test_unknown_start_or_occlusion_never_invents_order_violation():
    for start,occlusion in [('unknown',False),('empty_observed',True)]:
        e=RecipeEngine(load_recipe(),start);stable(e,{})
        if occlusion:e.feed(observation(3,600,usable=False))
        stable(e,{'cover':'cover_plate'},10,900)
        assert 'ORDER_VIOLATION' not in e.snapshot(True)['decision']['reason_codes']
        assert 'PARTIAL_OBSERVATION' in e.snapshot(True)['decision']['reason_codes']
def test_observably_missing_prerequisite_generates_order_event():
    e=RecipeEngine(load_recipe(),'empty_observed');stable(e,{})
    stable(e,{'cover':'cover_plate','spacer_left':'short_spacer'},3,600)
    assert any(v['reason_code']=='ORDER_VIOLATION' for v in e.events)
    assert e.snapshot(True)['decision']['status']=='REJECT_RECOMMENDATION'
def test_missing_only_rejected_at_explicit_final_checkpoint():
    e=RecipeEngine(load_recipe(),'empty_observed');stable(e,{})
    assert 'MISSING_COMPONENT' not in e.snapshot(False)['decision']['reason_codes']
    assert e.snapshot(True)['decision']['status']=='REJECT_RECOMMENDATION'
def test_wrong_part_then_correction_preserves_both_events():
    e=RecipeEngine(load_recipe(),'empty_observed');stable(e,{})
    stable(e,{'spacer_left':'long_spacer'},3,600)
    assert any(v['reason_code']=='WRONG_COMPONENT_CLASS' for v in e.events)
    stable(e,{'spacer_left':'short_spacer'},6,1200)
    assert any(v['reason_code']=='COMPONENT_CORRECTED' for v in e.events)
def test_actual_pixel_change_changes_detected_class():
    recipe=load_recipe();quad=[[0,0],[1,0],[1,1],[0,1]];f=np.full((480,640,3),220,np.uint8)
    cv2.circle(f,(179,153),17,(220,80,30),-1)
    a,_,_=analyze_frame(f,recipe,quad,0,0)
    cv2.rectangle(f,(144,146),(214,160),(220,80,30),-1)
    b,_,_=analyze_frame(f,recipe,quad,1,200)
    assert a['observations'][0]['class_id']=='short_spacer'
    assert b['observations'][0]['class_id']=='long_spacer'
def test_actual_dark_frame_abstains():
    record,_,_=analyze_frame(np.zeros((480,640,3),np.uint8),load_recipe(),[[0,0],[1,0],[1,1],[0,1]],0,0)
    assert record['quality']['usable'] is False
    assert all(r['class_id']=='unobserved' for r in record['observations'])

@pytest.fixture
def safety_client(tmp_path,monkeypatch):
    from reflex_safety import store,api
    from app.extension_main import app
    monkeypatch.setattr(store,'ROOT',tmp_path/'safety');monkeypatch.setattr(api,'FIXTURES',tmp_path/'fixtures')
    api.ENGINES.clear()
    with TestClient(app) as client:yield client
def create(client,**kwargs):
    r=client.post('/api/safety/sessions',json={'consent':True,**kwargs});assert r.status_code==201,r.text
    j=r.json();return j,{'Authorization':'Bearer '+j['access_token']}
def test_missing_benchmarks_are_explicit_and_legacy_routes_reachable(safety_client):
    c=safety_client
    assert c.get('/api/health').json()['opencv_version'].startswith('5.')
    assert c.get('/api/safety/benchmarks/runs').json()['real_video_benchmark']['status']=='NOT_RUN'
    assert c.get('/api/safety/recipes').json()['recipes'][0]['recipe_id']=='demo_panel_v1'
    assert c.get('/api/safety/sessions/nope').status_code==404
def test_consent_unknownfields_capability_and_report_escape(safety_client):
    c=safety_client
    assert c.post('/api/safety/sessions',json={'consent':False}).status_code==422
    assert c.post('/api/safety/sessions',json={'consent':True,'ground_truth':'PASS'}).status_code==422
    a,h=create(c);b,hb=create(c)
    assert c.get('/api/safety/sessions/'+a['id'],headers=hb).status_code==404
    assert c.get('/api/safety/sessions/'+a['id'],headers=h).status_code==200
    before=c.get('/api/safety/sessions/'+a['id'],headers=h).json()['decision']
    review=c.post(f"/api/safety/sessions/{a['id']}/acknowledgements",headers=h,json={'decision':'refute','note':'<script>alert(1)</script>'})
    assert review.json()['machine_decision_unchanged']
    assert c.get('/api/safety/sessions/'+a['id'],headers=h).json()['decision']==before
    report=c.get(f"/api/safety/sessions/{a['id']}/report?format=html",headers=h)
    assert '<script>alert(1)</script>' not in report.text and '&lt;script&gt;' in report.text
def test_unavailable_view_requests_input_without_fake_evidence(safety_client):
    c=safety_client;s,h=create(c)
    r=c.post(f"/api/safety/sessions/{s['id']}/reinspect",headers=h,json={'action':'REQUEST_SECOND_VIEW'}).json()
    assert r['state']=='waiting_for_input' and r['action']['executed'] is False
    assert r['child_session']['parent_session_id']==s['id']
    assert r['child_session']['evidence']==[]
def test_invalid_media_and_path_rejected(safety_client):
    c=safety_client;s,h=create(c)
    assert c.post(f"/api/safety/sessions/{s['id']}/video",headers=h,files={'file':('evil.mp4',b'not media','video/mp4')}).status_code==415
    assert c.get(f"/api/safety/sessions/{s['id']}/evidence/fake",headers=h).status_code==404
def test_frame_processing_ack_audit_and_cancel(safety_client):
    from reflex_safety import store
    c=safety_client;s,h=create(c,source_mode='LIVE_CAMERA')
    ok,jpg=cv2.imencode('.jpg',np.full((480,640,3),220,np.uint8));assert ok
    r=c.post(f"/api/safety/sessions/{s['id']}/frames",headers=h,data={'source_timestamp_ms':0},files={'file':('frame.jpg',jpg.tobytes(),'image/jpeg')})
    assert r.status_code==200,r.text
    assert r.json()['decision']['status']=='HOLD_FOR_REVIEW'
    evidence=r.json()['evidence'][0]
    assert c.get(evidence['overlay_url'],headers=h).status_code==200
    assert c.get(evidence['overlay_url']).status_code==404
    audit=store.audit(s['id']);previous='0'*64
    for event in audit:
        assert event['previous_sha256']==previous
        hashvalue=event['sha256'];payload={k:v for k,v in event.items() if k!='sha256'}
        assert hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()==hashvalue
        previous=hashvalue
    c.post(f"/api/safety/sessions/{s['id']}/cancel",headers=h)
    assert c.get('/api/safety/sessions/'+s['id'],headers=h).json()['state']=='cancelled'
    assert c.post(f"/api/safety/sessions/{s['id']}/frames",headers=h,data={'source_timestamp_ms':100},files={'file':('frame.jpg',jpg.tobytes(),'image/jpeg')}).status_code==409

def test_real_video_worker_evidence_and_immutable_input(safety_client,tmp_path):
    from reflex_safety.fixtures import render_frame
    from reflex_safety import api
    # Actual encoded pixel sequence, not a mocked response or test-label lookup.
    from reflex_safety.fixtures import SPLITS
    scenario=SPLITS['train'][0] if isinstance(SPLITS['train'][0],str) else SPLITS['train'][0]['scenario']
    path=tmp_path/'neutral.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(640,480))
    assert writer.isOpened()
    try:
        for i in range(60):writer.write(render_frame(scenario,i,12345)[0])
    finally:writer.release()
    data=path.read_bytes();c=safety_client;s,h=create(c,start_state='empty_observed')
    upload=c.post(f"/api/safety/sessions/{s['id']}/video",headers=h,files={'file':('../../neutral.avi',data,'video/x-msvideo')})
    assert upload.status_code==200,upload.text
    assert upload.json()['media']['sha256']==hashlib.sha256(data).hexdigest()
    assert c.post(f"/api/safety/sessions/{s['id']}/video",headers=h,files={'file':('again.avi',data,'video/x-msvideo')}).status_code==409
    assert c.post(f"/api/safety/sessions/{s['id']}/start",headers=h).status_code==202
    api.JOBS[s['id']].result(timeout=10)
    result=c.get(f"/api/safety/sessions/{s['id']}",headers=h).json()
    assert result['state']=='completed',result
    assert result['source_sha256']==hashlib.sha256(data).hexdigest()
    assert result['processing']['decoded_frames']==60
    assert result['evidence'] and result['observations']
    for evidence in result['evidence']:
        assert c.get(evidence['original_url'],headers=h).status_code==200
        assert c.get(evidence['overlay_url'],headers=h).status_code==200
    assert c.get(f"/api/safety/sessions/{s['id']}/media",headers=h).content==data
    assert c.post(f"/api/safety/sessions/{s['id']}/start",headers=h).status_code==409
