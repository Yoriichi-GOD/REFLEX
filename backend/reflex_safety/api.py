from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
import hashlib,html,json,os,threading
import cv2
from fastapi import APIRouter,File,Form,Header,HTTPException,UploadFile
from fastapi.responses import FileResponse,HTMLResponse
from pydantic import BaseModel,ConfigDict,Field
from app.core.image_io import decode_image,ImageInputError
from . import store
from .recipe import load_recipe,validate_quad
from .engine import analyze_video,RecipeEngine,DEFAULT_QUAD
from .vision import analyze_frame,MODEL_VERSION

router=APIRouter(prefix='/api/safety',tags=['Teaching-fixture Safety Station'])
POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='reflex-safety')
JOBS={};CANCEL={};ENGINES={};JOB_LOCK=threading.RLock()
FIXTURES=Path(os.getenv('REFLEX_SAFETY_FIXTURES',Path(__file__).resolve().parents[2]/'data/safety_fixtures')).resolve()

class Config(BaseModel):
    model_config=ConfigDict(extra='forbid')
    recipe_id: Literal['demo_panel_v1']='demo_panel_v1'
    policy: Literal['single','random','agent']='agent'
    source_mode: Literal['STREAM_REPLAY','LIVE_CAMERA','STILL_IMAGE']='STREAM_REPLAY'
    consent: bool
    calibration_quad: list[list[float]]=Field(default_factory=lambda:[p[:] for p in DEFAULT_QUAD])
    start_state: Literal['unknown','empty_observed']='unknown'
    final_checkpoint: bool=True
class Action(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['OBSERVE_NEXT_FRAMES','REQUEST_SECOND_VIEW']
class Finish(BaseModel):
    model_config=ConfigDict(extra='forbid')
    final_checkpoint: bool=True
class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['acknowledge','refute']
    note: str=Field(min_length=1,max_length=1000)

def access(sid,authorization):
    token=authorization[7:] if authorization and authorization.startswith('Bearer ') else ''
    try:return store.authorize(sid,token)
    except (KeyError,PermissionError):raise HTTPException(404,'Session not found or capability unavailable')
def idle(value):
    if value['state']=='running' or (value['id'] in JOBS and not JOBS[value['id']].done()):raise HTTPException(409,'Session is processing')
def mutable(value):
    idle(value)
    if value['state'] in ['completed','cancelled','failed']:raise HTTPException(409,'Session is terminal; create a new session to preserve its result')
async def read_file(file,limit):
    blocks=[];size=0
    while block:=await file.read(1024*1024):
        size+=len(block)
        if size>limit:raise HTTPException(413,'Upload exceeds configured size limit')
        blocks.append(block)
    return b''.join(blocks)

@router.get('/recipes')
def recipes():
    r=load_recipe();return {'recipes':[{**r.model_dump(),'sha256':r.sha256}]}

@router.get('/fixtures')
def fixtures():
    p=FIXTURES/'manifest.json'
    if not p.exists():return {'fixtures':[],'status':'NOT_GENERATED','source':'SYNTHETIC_SOFTWARE_TEST'}
    value=json.loads(p.read_text(encoding='utf-8'));rows=value if isinstance(value,list) else value.get('clips',[])
    return {'source':'SYNTHETIC_SOFTWARE_TEST','fixtures':[{'id':r['clip_id'],'name':r.get('name',r['clip_id']),'url':f"/api/safety/fixtures/{r['clip_id']}/media",'sha256':r['sha256'],'source':'SYNTHETIC_SOFTWARE_TEST'} for r in rows if r.get('split')=='test']}

@router.get('/fixtures/{fixture_id}/media')
def fixture_media(fixture_id:str):
    if not fixture_id or len(fixture_id)>64 or not all(c.isalnum() or c in '_-' for c in fixture_id):raise HTTPException(404)
    for path in FIXTURES.rglob('*.avi'):
        if path.stem==fixture_id:return FileResponse(path,media_type='video/x-msvideo',headers={'X-Reflex-Source':'SYNTHETIC_SOFTWARE_TEST'})
    raise HTTPException(404,'Fixture not found')

@router.post('/sessions',status_code=201)
def create(config:Config):
    if not config.consent:raise HTTPException(422,'Explicit permission to process this tabletop recording is required')
    try:validate_quad(config.calibration_quad);r=load_recipe(config.recipe_id)
    except ValueError as exc:raise HTTPException(422,str(exc))
    try:value,token=store.create({**config.model_dump(),'recipe':r.model_dump(),'recipe_sha256':r.sha256,'model_version':MODEL_VERSION,'cv_version':cv2.__version__})
    except ValueError as exc:raise HTTPException(429,str(exc))
    return {**store.public(value),'access_token':token}

@router.get('/sessions/{sid}')
def get(sid:str,authorization:str|None=Header(default=None)):return store.public(access(sid,authorization))

@router.post('/sessions/{sid}/video')
async def upload(sid:str,file:UploadFile=File(...),authorization:str|None=Header(default=None)):
    value=access(sid,authorization);mutable(value)
    if value['source_mode']!='STREAM_REPLAY':raise HTTPException(409,'Create a replay session for video uploads')
    if value.get('media'):raise HTTPException(409,'Input is immutable once attached')
    data=await read_file(file,50*1024**2)
    avi=data[:4]==b'RIFF' and data[8:12]==b'AVI ';mp4=len(data)>12 and data[4:8]==b'ftyp';webm=data[:4]==b'\x1aE\xdf\xa3'
    if not (avi or mp4 or webm):raise HTTPException(415,'Supported video container signature required:AVI,MP4,WebM')
    if file.content_type not in ['video/x-msvideo','video/avi','video/mp4','video/webm','application/octet-stream']:raise HTTPException(415,'Video MIME type required')
    ext='.avi' if avi else '.mp4' if mp4 else '.webm';path=store.directory(sid)/('input'+ext);path.write_bytes(data)
    cap=cv2.VideoCapture(str(path))
    try:opened=cap.isOpened();fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT);w=cap.get(cv2.CAP_PROP_FRAME_WIDTH);h=cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    finally:cap.release()
    if not opened or fps<=0 or count<=0 or count/fps>120 or w*h>5_000_000 or max(w,h)>2560:
        path.unlink();raise HTTPException(400,'Unreadable video or duration/dimensions exceed120seconds/5megapixels/2560edge')
    digest=hashlib.sha256(data).hexdigest();fixture_hashes={r['sha256'] for r in fixtures()['fixtures']}
    value.update(input_path=str(path),state='queued',media={'filename':'uploaded_recording'+ext,'sha256':digest,'bytes':len(data),'mime':'video/x-msvideo' if avi else 'video/mp4' if mp4 else 'video/webm','source':'SYNTHETIC_SOFTWARE_TEST' if digest in fixture_hashes else 'USER_SUPPLIED_UNBENCHMARKED','video_url':f'/api/safety/sessions/{sid}/media','fps_declared':fps,'source_duration_ms':count/fps*1000})
    store.save(value);store.append(sid,'VIDEO_ATTACHED',{'sha256':digest,'bytes':len(data),'source':value['media']['source']});return store.public(value)

def evidence_callback(sid):
    def callback(record,board,overlay):
        eid=record['evidence_id'];directory=store.directory(sid)/'evidence';directory.mkdir(exist_ok=True)
        for kind,img in [('original',board),('overlay',overlay)]:
            ok,encoded=cv2.imencode('.jpg',img,[cv2.IMWRITE_JPEG_QUALITY,85])
            if not ok:raise RuntimeError('Evidence encoding failed')
            (directory/f'{eid}_{kind}.jpg').write_bytes(encoded.tobytes())
        with store.LOCK:
            value=store.get(sid);value['progress']={'analyzed_frames':value['progress']['analyzed_frames']+1,'source_timestamp_ms':record['source_timestamp_ms'],'fraction':None};store.save(value)
        return {'original_url':f'/api/safety/sessions/{sid}/evidence/{eid}_original','overlay_url':f'/api/safety/sessions/{sid}/evidence/{eid}_overlay'}
    return callback

def run(sid):
    try:
        with store.LOCK:value=store.get(sid);value['state']='running';store.save(value)
        store.append(sid,'PROCESSING_STARTED',{'policy':value['policy'],'source_sha256':value['media']['sha256']})
        result=analyze_video(value['input_path'],load_recipe(value['recipe_id']),policy=value['policy'],calibration_quad=value['calibration_quad'],start_state=value['start_state'],final_checkpoint=value['final_checkpoint'],on_frame=evidence_callback(sid),cancel=CANCEL[sid].is_set)
        with store.LOCK:
            value=store.get(sid);value.update(result);value['state']='cancelled' if result['processing']['cancelled'] else 'completed';value['completed_at_utc']=store.utc();store.save(value)
        for event in result['events']:store.append(sid,'PROCEDURE_EVENT',event)
        for action in result['agent_trace']:store.append(sid,'INSPECTION_ACTION',action)
        store.append(sid,'PROCESSING_FINISHED',{'decision':result['decision'],'processing':{k:v for k,v in result['processing'].items() if k!='frame_processing_ms'}})
    except Exception as exc:
        with store.LOCK:
            value=store.get(sid);value.update(state='failed',error=type(exc).__name__,decision={'status':'HOLD_FOR_REVIEW','reason_codes':['PROCESSING_FAILED'],'required_human_action':'Check media validity and retry in a new session.'});store.save(value)
        store.append(sid,'PROCESSING_FAILED',{'exception_type':type(exc).__name__})

@router.post('/sessions/{sid}/start',status_code=202)
def start(sid:str,authorization:str|None=Header(default=None)):
    value=access(sid,authorization)
    with JOB_LOCK:
        if value['state']=='queued' and value.get('input_path'):
            if sum(not f.done() for f in JOBS.values())>=2:raise HTTPException(429,'Two clip jobs already active')
            if sid in JOBS:raise HTTPException(409,'Session already started')
            CANCEL[sid]=threading.Event();JOBS[sid]=POOL.submit(run,sid)
        else:raise HTTPException(409,'Attach one video before starting this session')
    return store.public(store.get(sid))

@router.post('/sessions/{sid}/cancel')
def cancel(sid:str,authorization:str|None=Header(default=None)):
    value=access(sid,authorization)
    with JOB_LOCK:
        if sid in CANCEL and not JOBS[sid].done():CANCEL[sid].set()
        elif value['state'] not in ['completed','failed','cancelled']:
            value['state']='cancelled';value['decision']={'status':'HOLD_FOR_REVIEW','reason_codes':['CANCELLED'],'required_human_action':'Start a new session to inspect again.'};store.save(value)
    store.append(sid,'CANCEL_REQUESTED',{});return store.public(store.get(sid))

@router.get('/sessions/{sid}/events')
def events(sid:str,authorization:str|None=Header(default=None)):
    value=access(sid,authorization);return {'events':value['events'],'audit':store.audit(sid)}

@router.get('/sessions/{sid}/media')
def media(sid:str,authorization:str|None=Header(default=None)):
    value=access(sid,authorization)
    if not value.get('input_path'):raise HTTPException(404,'No video attached')
    return FileResponse(value['input_path'],media_type=value['media']['mime'],headers={'Cache-Control':'no-store'})

@router.get('/sessions/{sid}/evidence/{eid}')
def evidence(sid:str,eid:str,authorization:str|None=Header(default=None)):
    access(sid,authorization)
    if len(eid)>100 or not all(c.isalnum() or c in '_-' for c in eid):raise HTTPException(404)
    p=store.directory(sid)/'evidence'/f'{eid}.jpg'
    if not p.is_file():raise HTTPException(404,'Evidence not found')
    return FileResponse(p,media_type='image/jpeg',headers={'Cache-Control':'no-store'})

@router.post('/sessions/{sid}/frames')
async def frame(sid:str,file:UploadFile=File(...),source_timestamp_ms:float=Form(...),authorization:str|None=Header(default=None)):
    value=access(sid,authorization);mutable(value)
    if value['source_mode']=='STREAM_REPLAY':raise HTTPException(409,'Use video processing for replay sessions')
    if not (0<=source_timestamp_ms<=120000):raise HTTPException(422,'Capture timestamps must be within120seconds')
    if value['progress']['analyzed_frames']>=200:raise HTTPException(429,'Frame budget exhausted')
    data=await read_file(file,12*1024**2)
    try:image,_=decode_image(data)
    except (ImageInputError,ValueError):raise HTTPException(400,'Invalid frame image')
    with store.LOCK:
        engine=ENGINES.get(sid)
        if engine is None:
            if value['progress']['analyzed_frames']:raise HTTPException(409,'Live state was interrupted; create a new session')
            engine=RecipeEngine(load_recipe(value['recipe_id']),value['start_state']);ENGINES[sid]=engine
        index=value['progress']['analyzed_frames'];record,board,overlay=analyze_frame(image,engine.recipe,value['calibration_quad'],index,source_timestamp_ms)
        record.update(evidence_id=f"frame-{index:05d}-{record['frame_sha256'][:12]}",source_id='uploaded_frames',capture_kind='user_uploaded_camera_frame' if value['source_mode']=='LIVE_CAMERA' else 'user_uploaded_still')
        try:engine.feed(record)
        except ValueError as exc:raise HTTPException(422,str(exc))
        entry={k:record[k] for k in ['frame_index','source_timestamp_ms','frame_sha256','quality','processing_ms']};entry['id']=record['evidence_id'];entry.update(evidence_callback(sid)(record,board,overlay))
        value=store.get(sid);value.update(engine.snapshot());value['evidence'].append(entry);value['state']='waiting_for_input';value['media']={'filename':'camera_frames','sha256':None,'bytes':None,'mime':'image/jpeg','source':'USER_SUPPLIED_UNBENCHMARKED'};store.save(value)
    store.append(sid,'FRAME_PROCESSED',{'evidence_id':entry['id'],'frame_sha256':record['frame_sha256'],'source_timestamp_ms':source_timestamp_ms,'cv_version':cv2.__version__});return store.public(value)

@router.post('/sessions/{sid}/finish')
def finish(sid:str,config:Finish,authorization:str|None=Header(default=None)):
    value=access(sid,authorization);mutable(value)
    if sid not in ENGINES:raise HTTPException(409,'No frame session to finish')
    value.update(ENGINES[sid].snapshot(config.final_checkpoint));value['state']='completed';value['completed_at_utc']=store.utc();store.save(value);store.append(sid,'FRAME_SESSION_FINISHED',{'decision':value['decision']});return store.public(value)

@router.post('/sessions/{sid}/reinspect')
def reinspect(sid:str,config:Action,authorization:str|None=Header(default=None)):
    value=access(sid,authorization);idle(value)
    if sum(a.get('action') in ['REQUEST_SECOND_VIEW','OBSERVE_NEXT_FRAMES'] for a in value['agent_trace'])>=4:raise HTTPException(429,'Manual reinspection request budget exhausted')
    child_cfg={k:value[k] for k in ['recipe_id','policy','consent','calibration_quad','final_checkpoint']};child_cfg.update(source_mode='STILL_IMAGE',start_state='unknown')
    try:child,token=store.create({**child_cfg,'recipe':value['recipe'],'recipe_sha256':value['recipe_sha256'],'model_version':MODEL_VERSION,'cv_version':cv2.__version__,'parent_session_id':sid,'requested_action':config.action})
    except ValueError as exc:raise HTTPException(429,str(exc))
    action={'action':config.action,'executed':False,'reason':'A fresh supplied frame or second viewpoint is required; no unseen pixels were generated.','child_session_id':child['id'],'requires_new_input':True,'cost_ms':0}
    value['agent_trace'].append(action);store.save(value);store.append(sid,'REINSPECTION_INPUT_REQUESTED',action)
    return {'state':'waiting_for_input','parent_session_id':sid,'child_session':{**store.public(child),'access_token':token},'action':action}

@router.post('/sessions/{sid}/acknowledgements')
def acknowledge(sid:str,review:Review,authorization:str|None=Header(default=None)):
    with store.LOCK:
        value=access(sid,authorization);record=store.append(sid,'HUMAN_REVIEW',review.model_dump());value['acknowledgements'].append(record);store.save(value)
    return {'acknowledgement':record,'machine_decision_unchanged':True,'session':store.public(value)}

@router.get('/sessions/{sid}/report')
def report(sid:str,format:Literal['json','html']='json',authorization:str|None=Header(default=None)):
    value=store.public(access(sid,authorization));value['audit']=store.audit(sid)
    if format=='json':return value
    body=html.escape(json.dumps(value,indent=2,ensure_ascii=False))
    return HTMLResponse('<!doctype html><html><meta charset="utf-8"><title>REFLEX Safety Station report</title><style>body{font:16px system-ui;max-width:1000px;margin:30px}pre{white-space:pre-wrap;word-break:break-word}</style><h1>REFLEX — advisory teaching-fixture report</h1><p>Use the browser print dialog to export this actual report as PDF. Machine findings and human review remain separate. No industrial safety certification.</p><pre>'+body+'</pre></html>',headers={'Cache-Control':'no-store'})

@router.delete('/sessions/{sid}',status_code=204)
def delete(sid:str,authorization:str|None=Header(default=None)):
    value=access(sid,authorization);idle(value)
    with JOB_LOCK:ENGINES.pop(sid,None);store.delete(sid)

@router.get('/benchmarks/runs')
def benchmark_runs():
    p=Path(__file__).resolve().parents[2]/'benchmarks/procedural_safety/results.json'
    return {'runs':[{'run_id':'synthetic_software_v1','source':'SYNTHETIC_SOFTWARE_TEST','url':'/api/safety/benchmarks/runs/synthetic_software_v1'}] if p.exists() else [],'real_video_benchmark':{'status':'NOT_RUN','reason':'No authorized recorded physical fixture clips or matched external video/labels available'}}

@router.get('/benchmarks/runs/{run_id}')
def benchmark_run(run_id:str):
    p=Path(__file__).resolve().parents[2]/'benchmarks/procedural_safety/results.json'
    if run_id!='synthetic_software_v1' or not p.exists():raise HTTPException(404,'Benchmark not run')
    return json.loads(p.read_text(encoding='utf-8'))
