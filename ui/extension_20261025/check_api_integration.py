"""Real wrapper/API and pixel-evidence checks; no browser interaction claim."""
import hashlib,json,os,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(os.getenv('REFLEX_UI_TEST_ROOT',Path(__file__).resolve().parents[2]))
OUT=Path(os.getenv('REFLEX_UI_TEST_OUTPUT',ROOT/'reports/extension_20261025/ui-api-check'))
OUT.mkdir(parents=True,exist_ok=True)
os.environ['REFLEX_DATA_DIR']=str(OUT/'legacy-runtime')
os.environ['MODEL_DIR']=str(ROOT/'data/model')
os.environ['REFLEX_SAFETY_DATA_DIR']=str(OUT/'safety-runtime')
sys.path.insert(0,str(ROOT/'backend'))
import cv2,numpy as np
from fastapi.testclient import TestClient
from app.extension_main import app

checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)

with TestClient(app) as client:
    home=client.get('/');page=client.get('/safety')
    check('legacy_studio_and_additive_entry_serve',home.status_code==200 and page.status_code==200 and 'href="/safety"'in home.text)
    check('page_keeps_solar_assets_and_isolated_script','reflex-solar-logo.webp'in page.text and '/safety-assets/safety.js'in page.text and '/app.js'not in page.text)
    for asset,content_type in [('safety.js','javascript'),('safety.css','text/css')]:
        response=client.get('/safety-assets/'+asset)
        check(asset+'_served_exact_bytes',response.status_code==200 and response.content==(ROOT/'frontend'/asset).read_bytes() and content_type in response.headers['content-type'])
    for p in ['/styles.css','/assets-ui/reflex-solar-logo.webp','/assets-ui/reflex-space-background.webp','/assets-ui/reflex-orbital-planet.webp']:
        check('shared_asset_'+p,client.get(p).status_code==200)
    recipe=client.get('/api/safety/recipes').json()['recipes'][0]
    config={'recipe_id':recipe['recipe_id'],'policy':'agent','source_mode':'STILL_IMAGE','consent':True,'calibration_quad':[[0,0],[1,0],[1,1],[0,1]],'start_state':'unknown','final_checkpoint':False}
    run=client.post('/api/safety/sessions',json=config).json();sid=run['id'];headers={'Authorization':'Bearer '+run['access_token']};base='/api/safety/sessions/'+sid
    check('session_capability_required',client.get(base).status_code==404 and client.get(base,headers=headers).status_code==200)
    image=np.full((480,640,3),220,np.uint8);cv2.circle(image,(179,153),17,(220,80,30),-1)
    ok,encoded=cv2.imencode('.jpg',image);assert ok
    response=client.post(base+'/frames',headers=headers,data={'source_timestamp_ms':'0'},files={'file':('not_a_label.jpg',encoded.tobytes(),'image/jpeg')})
    check('actual_pixel_frame_processed',response.status_code==200)
    first=response.json();entry=first['evidence'][0]
    check('evidence_uses_actual_cv5_pixels',first['cv_version'].startswith('5.') and len(first['observations'])>0 and entry['frame_sha256'])
    for key in ['original_url','overlay_url']:
        evidence=client.get(entry[key],headers=headers)
        check('protected_'+key,evidence.status_code==200 and evidence.headers['content-type'].startswith('image/') and client.get(entry[key]).status_code==404 and cv2.imdecode(np.frombuffer(evidence.content,np.uint8),cv2.IMREAD_COLOR)is not None)
    final=client.post(base+'/finish',headers=headers,json={'final_checkpoint':False}).json()
    check('still_abstains_instead_of_inventing_temporal_pass',final['state']=='completed' and final['decision']['status']=='HOLD_FOR_REVIEW')
    before=final['decision'];review=client.post(base+'/acknowledgements',headers=headers,json={'decision':'refute','note':'Operator test: <script>untrusted</script>'}).json()
    after=client.get(base,headers=headers).json()
    check('review_appended_original_decision_retained',review['machine_decision_unchanged'] and after['decision']==before and len(after['acknowledgements'])==1)
    for fmt in ['json','html']:
        report=client.get(base+'/report?format='+fmt,headers=headers)
        check('actual_report_'+fmt,report.status_code==200 and run['access_token']not in report.text and ('<script>untrusted</script>'not in report.text if fmt=='html'else report.json()['id']==sid))
    child=client.post(base+'/reinspect',headers=headers,json={'action':'REQUEST_SECOND_VIEW'}).json()['child_session']
    check('second_view_requires_real_child_input',child['parent_session_id']==sid and child['evidence']==[] and child['source_mode']=='STILL_IMAGE')
    check('parent_capability_cannot_read_child',client.get('/api/safety/sessions/'+child['id'],headers=headers).status_code==404)
    check('explicit_real_video_benchmark_not_run',client.get('/api/safety/benchmarks/runs').json()['real_video_benchmark']['status']=='NOT_RUN')

receipt={'utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','scope':'Actual FastAPI wrapper, static assets and OpenCV pixel evidence; not rendered browser, physical camera or physical-assembly validation','checks':checks,'check_count':len(checks),'session_ids':[sid,child['id']],'no_tokens_recorded':True,'original_app_js_sha256':hashlib.sha256((ROOT/'frontend/app.js').read_bytes()).hexdigest(),'original_styles_css_sha256':hashlib.sha256((ROOT/'frontend/styles.css').read_bytes()).hexdigest()}
(OUT/'RESULTS.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print(json.dumps(receipt))
