"""Per-session capabilities, atomic snapshots, append-only hash-chained audit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,secrets,threading,uuid
ROOT=Path(os.getenv('REFLEX_SAFETY_DATA_DIR',Path(__file__).resolve().parents[2]/'data/safety')).resolve()
LOCK=threading.RLock()
def utc():return datetime.now(timezone.utc).isoformat()
def directory(sid):
    if len(sid)!=32 or not all(c in '0123456789abcdef' for c in sid):raise KeyError('Session not found')
    return ROOT/sid
def save(value):
    with LOCK:
        d=directory(value['id']);d.mkdir(parents=True,exist_ok=True);p=d/'session.tmp'
        p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');os.replace(p,d/'session.json')
def get(sid):
    with LOCK:
        p=directory(sid)/'session.json'
        if not p.is_file():raise KeyError('Session not found')
        return json.loads(p.read_text(encoding='utf-8'))
def create(config):
    with LOCK:
        ROOT.mkdir(parents=True,exist_ok=True)
        if len(list(ROOT.glob('*/session.json')))>=50:raise ValueError('Session quota reached; delete an old session')
        if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>1024**3:raise ValueError('Safety storage quota reached')
        sid=uuid.uuid4().hex;token=secrets.token_urlsafe(32)
        value={**config,'id':sid,'created_at_utc':utc(),'state':'waiting_for_input','access_token_sha256':hashlib.sha256(token.encode()).hexdigest(),'media':None,'events':[],'observations':[],'agent_trace':[],'evidence':[],'acknowledgements':[],'progress':{'analyzed_frames':0,'source_timestamp_ms':None,'fraction':None},'decision':{'status':'HOLD_FOR_REVIEW','reason_codes':['NO_INPUT'],'required_human_action':'Supply a consented calibrated fixture recording.'},'recipe_state':None,'processing':None}
        save(value);append(sid,'SESSION_CREATED',{'source_mode':value['source_mode'],'policy':value['policy']});return value,token
def authorize(sid,token):
    value=get(sid)
    if not token or not secrets.compare_digest(value['access_token_sha256'],hashlib.sha256(token.encode()).hexdigest()):raise PermissionError('Invalid session capability')
    return value
def public(value):return {k:v for k,v in value.items() if k not in ['access_token_sha256','input_path']}
def append(sid,kind,payload):
    with LOCK:
        p=directory(sid)/'audit.jsonl';previous='0'*64
        if p.exists():
            lines=p.read_text(encoding='utf-8').splitlines()
            if lines:previous=json.loads(lines[-1])['sha256']
        record={'event_id':uuid.uuid4().hex,'utc':utc(),'kind':kind,'payload':payload,'previous_sha256':previous}
        record['sha256']=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with p.open('a',encoding='utf-8') as f:f.write(json.dumps(record,separators=(',',':'))+'\n')
        return record
def audit(sid):
    p=directory(sid)/'audit.jsonl';return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []
def recover():
    ROOT.mkdir(parents=True,exist_ok=True)
    for p in ROOT.glob('*/session.json'):
        value=get(p.parent.name)
        if value['state'] in ['running','queued']:
            value.update(state='failed',decision={'status':'HOLD_FOR_REVIEW','reason_codes':['WORKER_INTERRUPTED'],'required_human_action':'Replay the original input in a new session.'});save(value);append(value['id'],'WORKER_INTERRUPTED',{})
def delete(sid):
    import shutil
    d=directory(sid);assert d.parent==ROOT and d.resolve().parent==ROOT;shutil.rmtree(d)
