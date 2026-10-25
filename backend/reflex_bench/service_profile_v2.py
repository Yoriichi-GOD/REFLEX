"""Controlled loopback HTTP profiling inside one actual local/Fargate runtime.

The public upload limit is unchanged. The benchmark server binds only127.0.0.1,
has no published port, uses public VisA inputs, and exits after finite requests.
Loopback latency must never be called external internet/browser roundtrip.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import threading

import httpx
import numpy as np

from reflex_bench.runtime_stats_v2 import memory_snapshot

OUTPUT_LOCK=threading.RLock()


def stats(values):
    values=[float(v) for v in values]
    return {"n":len(values),"mean_ms":float(np.mean(values)),"std_ms":float(np.std(values)),
            "p50_ms":float(np.quantile(values,.5)),"p90_ms":float(np.quantile(values,.9)),
            "p95_ms":float(np.quantile(values,.95)),"max_ms":max(values)}


def server_memory(pid):
    if os.name!='nt':
        text=Path(f'/proc/{pid}/status').read_text()
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in text.splitlines() if ':' in line}
        return {"rss_bytes":int(fields['VmRSS'].split()[0])*1024,"peak_rss_bytes":int(fields['VmHWM'].split()[0])*1024}
    import ctypes
    from ctypes import wintypes
    size=ctypes.c_size_t
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,size) for n in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.restype=wintypes.HANDLE;kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        c=Counters();c.cb=ctypes.sizeof(c)
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb):raise ctypes.WinError(ctypes.get_last_error())
        return {"rss_bytes":int(c.WorkingSetSize),"peak_rss_bytes":int(c.PeakWorkingSetSize)}
    finally:kernel.CloseHandle(handle)


def emit(value):
    with OUTPUT_LOCK:print(json.dumps(value,separators=(',',':')),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--v1-profiles',type=Path,required=True);p.add_argument('--v2-profiles',type=Path,required=True)
    p.add_argument('--weights',type=Path,required=True);p.add_argument('--rounds',type=int,default=3);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    fixtures=json.loads(a.fixtures.read_text())
    assert len(fixtures)==100 and a.rounds in (1,3)
    for label,directory in (('v1',a.v1_profiles),('v2',a.v2_profiles)):
        for category in ('candle','cashew'):
            if not (directory/category/'metadata.json').exists():
                raise ValueError(f'{label} profile root must directly contain{category}/metadata.json; received{directory}')
    all_rows=[];summaries={}
    environment={'python':sys.version,'platform':sys.platform,'logical_cpus':os.cpu_count(),**memory_snapshot(),
                 'cpu_model':next((s.split(':',1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),'unavailable') if sys.platform=='linux' else os.getenv('PROCESSOR_IDENTIFIER','unavailable')}
    import cv2
    environment['opencv']=cv2.__version__
    environment['runtime']=os.getenv('REFLEX_RUNTIME','local')
    if sys.platform=='linux':
        for field,path in (('cgroup_cpu_max','/sys/fs/cgroup/cpu.max'),('cgroup_memory_max','/sys/fs/cgroup/memory.max')):
            environment[field]=Path(path).read_text().strip() if Path(path).exists() else 'unavailable'
    for variant,profiles in (('v1',a.v1_profiles),('v2',a.v2_profiles)):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env=os.environ.copy();env.pop('REFLEX_V2_FEATURE_CACHE',None)
        fallback=a.root/'synthetic-profile'
        if not (fallback/'normal_bank.npz').exists():fallback=a.root/'data/model'
        if not (fallback/'normal_bank.npz').exists():raise RuntimeError('Verified synthetic fallback profile missing; no benchmark bootstrap fitting allowed')
        env.update(PYTHONPATH=str(a.root/'backend'),REFLEX_PROFILES_DIR=str(profiles),REFLEX_DEFAULT_PROFILE='candle',
                   REFLEX_ONNX_WEIGHTS=str(a.weights),REFLEX_DATA_DIR=str(a.out/variant/'data'),MODEL_DIR=str(fallback),
                   UPLOADS_PER_WINDOW='2000',UPLOAD_RATE_WINDOW_SECONDS='600',BUILD_COMMIT='v2-isolated-http-benchmark',
                   OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',REFLEX_BENCHMARK_MODE='1')
        (a.out/variant).mkdir()
        log=(a.out/variant/'server.log').open('w',encoding='utf-8')
        start=time.perf_counter()
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--app-dir',str(a.root/'backend'),
                               '--host','127.0.0.1','--port',str(port)],env=env,cwd=a.root,stdout=log,stderr=subprocess.STDOUT)
        try:
            last_ready_error=None
            for _ in range(120):
                if proc.poll() is not None:raise RuntimeError(f'{variant} server exited; inspect own server.log')
                try:
                    r=httpx.get(base+'/api/ready',timeout=1)
                    if r.status_code==200:break
                    last_ready_error=f'{r.status_code}:{r.text[:300]}'
                except httpx.RequestError:pass
                time.sleep(.5)
            else:raise RuntimeError(f'Readiness timeout; last response={last_ready_error}')
            ready_ms=(time.perf_counter()-start)*1000
            rows=[]
            def request(fixture,phase,round_number,index,concurrency):
                path=Path(fixture['path'])
                if not path.exists():path=a.root/'benchmark-inputs'/fixture['category']/fixture['case_id']
                raw=path.read_bytes()
                import hashlib
                assert hashlib.sha256(raw).hexdigest()==fixture['sha256']
                start=time.perf_counter()
                r=httpx.post(base+'/api/inspections',data={'category':fixture['category']},files={'file':('case.jpg',raw,'image/jpeg')},timeout=120)
                elapsed=(time.perf_counter()-start)*1000
                row={'variant':variant,'phase':phase,'round':round_number,'index':index,'concurrency':concurrency,
                     'category':fixture['category'],'case_id':fixture['case_id'],'image_sha256':fixture['sha256'],
                     'utc':datetime.now(timezone.utc).isoformat(),'http_status':r.status_code,'loopback_http_ms':elapsed}
                if r.status_code==200:
                    value=r.json()
                    assert value['image_sha256']==fixture['sha256']
                    row.update(inspection_id=value['id'],request_id=r.headers.get('x-request-id'),
                               server_handler_ms=float(r.headers['x-reflex-server-ms']),runtime_ms=value['runtime_ms'],
                               stage_timings=value.get('stage_timings'),model_version=value['model_version'],
                               normal_bank_sha256=value['normal_bank_sha256'],decision=value['decision'],
                               second_look=bool(value.get('crop_evidence')),server_pid=int(r.headers['x-reflex-process-id']),
                               **server_memory(int(r.headers['x-reflex-process-id'])))
                else:row['error_excerpt']=r.text[:200]
                emit({'event':'service_profile_sample',**row})
                with OUTPUT_LOCK:
                    with (a.out/'samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
                return row
            for index in range(10):rows.append(request(fixtures[index],'warmup',0,index,1))
            for round_number in range(a.rounds):
                batch_start=time.perf_counter()
                for index,fixture in enumerate(fixtures):rows.append(request(fixture,'measured',round_number,index,1))
                emit({'event':'service_profile_round','variant':variant,'round':round_number,'seconds':time.perf_counter()-batch_start,'n':100})
            batch_start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(request,f,'concurrency',0,i,2) for i,f in enumerate(fixtures)]
                rows.extend(f.result() for f in futures)
            concurrent_seconds=time.perf_counter()-batch_start
            success=[r for r in rows if r['phase']=='measured' and r['http_status']==200]
            concurrent=[r for r in rows if r['phase']=='concurrency' and r['http_status']==200]
            stage_names=sorted({key for r in success for key,value in (r.get('stage_timings') or {}).items() if isinstance(value,(int,float)) and key!='feature_cache_hit'})
            summaries[variant]={'readiness_ms':ready_ms,'measured_count':len(success),'failed_requests':sum(r['http_status']!=200 for r in rows),
                                'latency':{k:stats([r[k] for r in success]) for k in ('loopback_http_ms','server_handler_ms','runtime_ms')},
                                'stage_timings':{k:stats([r['stage_timings'][k] for r in success if k in (r.get('stage_timings') or {})]) for k in stage_names},
                                'max_observed_rss_bytes':max(r.get('rss_bytes',0) for r in rows),
                                'peak_rss_bytes':max(r.get('peak_rss_bytes',0) for r in rows),
                                'concurrency2':{'requests':len(concurrent),'elapsed_seconds':concurrent_seconds,'observed_requests_per_second':len(concurrent)/concurrent_seconds,
                                                'latency':stats([r['loopback_http_ms'] for r in concurrent])}}
            all_rows.extend(rows)
        finally:
            if os.name=='nt' and proc.poll() is None:
                subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,check=False)
            else:proc.terminate()
            try:proc.wait(timeout=15)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close()
    summary={'event':'service_profile_summary','utc':datetime.now(timezone.utc).isoformat(),'environment':environment,
             'scope':'Isolated actual backend;localhostHTTP only,notexternalnetworkorpublicservicecapacity;publicguardunchanged;dedicatedbenchmarklistener127.0.0.1',
             'inputs':100,'warmups_per_variant':10,'repeat_rounds':a.rounds,'summaries':summaries}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2));emit(summary)


if __name__=='__main__':main()
