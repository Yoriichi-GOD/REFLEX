"""Public real-photo profile obeying the existing10uploads/600secguard.

100 deterministic, non-cherry-picked real images after10warmups. No deployment
changes, concurrency1; observed throughput is explicitly pacing limited.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time

import httpx
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
URL="https://re-c0a0c131729f4898bb80d160feb0ccc7.ecs.ap-southeast-2.on.aws"


def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--data",type=Path,required=True)
    p.add_argument("--resume",action="store_true",help="Continue verified successful checkpoints, preserving the interruption")
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=a.resume)
    fixtures=[]
    for category in ("candle","cashew"):
        rows=list(csv.DictReader((ROOT/f"reports/improvement_20261024/{category}/per_case.csv").open()))
        for label in (0,1):
            for row in [r for r in rows if int(r["label"])==label][:25]:
                path=a.data/category/"test"/row["case_id"]
                assert hashlib.sha256(path.read_bytes()).hexdigest()==row["image_sha256"]
                fixtures.append({"category":category,"case_id":row["case_id"],"path":str(path),"sha256":row["image_sha256"]})
    assert len(fixtures)==100
    if a.resume:
        assert json.loads((a.out/"fixtures.json").read_text())==fixtures,"Fixture membership changed"
    else:(a.out/"fixtures.json").write_text(json.dumps(fixtures,indent=2))
    state={"status":"RUNNING","started_utc":datetime.now(timezone.utc).isoformat(),"warmup_target":10,"measured_target":100,
           "base_url":URL,"region":"ap-southeast-2","concurrency":1,"minimum_gap_seconds":62,
           "scope":"100realVisAimages;fixedfirst25normal/25defectpercategory;realimagesnotadditionalaccuracytest;10warmups;throughputpacinglimited",
           "data_retention":"Public demo temporary storage24h or earlier replacement; only attributed publicVisAimages",
           "attempts":[],"warmups":[],"measured":[]}
    if a.resume:
        original=(a.out/"state.json").read_bytes()
        state=json.loads(original)
        assert state["status"]=="RUNNING", "Only an interrupted successful run can resume"
        assert all(r.get("http_status")==200 and not r.get("error") for r in state["attempts"])
        assert len(state["attempts"])==len(state["warmups"])+len(state["measured"])
        archive=a.out/f"interrupted-state-{len(state['attempts']):03d}.json"
        with archive.open("xb") as f:f.write(original)
        state.setdefault("interruptions",[]).append({"resumed_utc":datetime.now(timezone.utc).isoformat(),
            "completed_attempts":len(state["attempts"]),"previous_last_utc":state["attempts"][-1]["utc"],
            "reason":"Local worker stopped during interrupted session; no failed attempt is suppressed"})
    def save():
        tmp=a.out/"state.tmp";tmp.write_text(json.dumps(state,indent=2));tmp.replace(a.out/"state.json")
    with httpx.Client(timeout=30) as client:
        health=client.get(URL+"/api/health");health.raise_for_status()
        if a.resume:
            assert health.json()["build_revision"]==state["build_revision"],"Build changed across interruption"
            state["resume_health"]=health.json()
        else:state["initial_health"]=health.json()
    save()
    last=None
    tasks=fixtures[:10]+fixtures
    for index,fixture in enumerate(tasks):
        if index<len(state["attempts"]):
            previous=state["attempts"][index]
            assert previous["index"]==index and previous["image_sha256"]==fixture["sha256"]
            continue
        if last is not None:
            delay=max(0,62-(time.monotonic()-last))
            if delay:time.sleep(delay)
        raw=Path(fixture["path"]).read_bytes()
        phase="warmup" if index<10 else "measured"
        item={"index":index,"phase":phase,"category":fixture["category"],"case_id":fixture["case_id"],"image_sha256":fixture["sha256"],"utc":datetime.now(timezone.utc).isoformat()}
        start=time.perf_counter()
        try:
            with httpx.Client(timeout=120,headers={"Connection":"close"}) as client:
                r=client.post(URL+"/api/inspections",data={"category":fixture["category"]},files={"file":("benchmark.jpg",raw,"image/jpeg")})
            item.update(http_status=r.status_code,http_roundtrip_ms=(time.perf_counter()-start)*1000,request_id=r.headers.get("X-Request-ID"))
            if r.status_code!=200:
                item["error_excerpt"]=r.text[:300]
                raise RuntimeError(f"HTTP{r.status_code}; stopping rather than bypassing guard")
            payload=r.json()
            assert payload["image_sha256"]==fixture["sha256"] and payload["synthetic"] is False
            if "build_revision" not in state:state["build_revision"]=payload["build_revision"]
            assert payload["build_revision"]==state["build_revision"],"Build changed during profile"
            item.update(inspection_id=payload["id"],server_runtime_ms=payload["runtime_ms"],
                        model_version=payload["model_version"],model_sha256=payload["normal_bank_sha256"],
                        decision=payload["decision"],source_dimensions=payload["source_dimensions"],
                        server_header_ms=r.headers.get("X-Reflex-Server-Ms"),stage_timings=payload.get("stage_timings"))
            state[phase+"s" if phase=="warmup" else phase].append(item)
        except Exception as exc:
            item["error"]=f"{type(exc).__name__}:{exc}";state["status"]="STOPPED_ERROR"
            state["attempts"].append(item);save();raise
        last=time.monotonic();state["attempts"].append(item);save()
        print(json.dumps({"phase":phase,"index":index+1,"count":len(state["measured"]),"ms":item["http_roundtrip_ms"],"runtime_ms":item["server_runtime_ms"]}),flush=True)
    def stats(values):
        return {"n":len(values),"mean_ms":float(np.mean(values)),"std_ms":float(np.std(values)),
                "p50_ms":float(np.quantile(values,.5)),"p90_ms":float(np.quantile(values,.9)),
                "p95_ms":float(np.quantile(values,.95)),"max_ms":max(values)}
    state.update(status="COMPLETED",finished_utc=datetime.now(timezone.utc).isoformat(),
                 measured_statistics={k:stats([r[k] for r in state["measured"]]) for k in ("http_roundtrip_ms","server_runtime_ms")})
    save();(a.out/"summary.json").write_text(json.dumps({k:v for k,v in state.items() if k not in ("attempts","measured","warmups")},indent=2))
    print(json.dumps(state["measured_statistics"]),flush=True)


if __name__=="__main__":main()
