"""Verify a deployed real-image demo without treating smoke cases as a benchmark."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import time

import cv2
import httpx
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument("url");parser.add_argument("--tag",required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();base=args.url.rstrip("/")
    client=httpx.Client(base_url=base,timeout=60)
    health=client.get("/api/health");health.raise_for_status();health_data=health.json()
    assert health_data["build_revision"]==args.tag and health_data["runtime"]=="aws"
    assert health_data["opencv_version"].startswith("5.") and health_data["model_mode"]=="opencv_dnn_patch_memory"
    profiles=client.get("/api/profiles").json()["profiles"]
    assert {p["category"] for p in profiles}=={"candle","cashew","synthetic_machined_plate"}
    page=client.get("/");page.raise_for_status()
    script=client.get("/app.js");script.raise_for_status()
    assert 'data-layer="compare"' in page.text
    assert 'Original photograph' in script.text and 'Anomaly heatmap' in script.text
    stylesheet=re.search(r'href="([^\"]+\.css[^\"]*)"',page.text).group(1)
    css=client.get(stylesheet);css.raise_for_status()
    static_urls=set(re.findall(r'url\([\'\"]?(/[^)\'\"]+)',css.text))
    static_urls|=set(re.findall(r'(?:src|href)="(/assets-ui/[^\"]+)"',page.text))
    static_checks=[]
    for url in sorted(static_urls):
        response=client.get(url);response.raise_for_status()
        local=ROOT/"frontend"/url.lstrip("/").split("?")[0]
        assert local.exists() and hashlib.sha256(response.content).hexdigest()==hashlib.sha256(local.read_bytes()).hexdigest()
        static_checks.append({"url":url,"status":response.status_code,"sha256":hashlib.sha256(response.content).hexdigest(),"bytes":len(response.content)})
    for name,response in (("index.html",page),("app.js",script),("styles.css",css)):
        assert hashlib.sha256(response.content).hexdigest()==hashlib.sha256((ROOT/"frontend"/name).read_bytes()).hexdigest()
    audit=json.loads((ROOT/"reports"/"real_demo_20261024"/"fixture_audit.json").read_text())
    expected={c["demo_id"]:c for c in audit["cases"]}
    samples=[]
    for category in ("candle","cashew"):
        cases=client.get("/api/demo-cases",params={"category":category}).json()["cases"]
        assert len(cases)==3
        evaluation=client.get("/api/evaluations/latest",params={"category":category}).json()
        assert evaluation["synthetic"] is False and category in evaluation["dataset"]
        for case in cases:
            source=client.get(case["image_url"]);source.raise_for_status()
            assert hashlib.sha256(source.content).hexdigest()==case["sha256"]
            started=time.perf_counter()
            response=client.post("/api/inspections",data={"category":category},files={"file":(case["id"]+".jpg",source.content,"image/jpeg")})
            end_to_end_ms=(time.perf_counter()-started)*1000
            response.raise_for_status();result=response.json()
            assert result["class_name"]==category and result["synthetic"] is False
            assert result["model_mode"]=="opencv_dnn_patch_memory" and result["demo_attribution"]["dataset"]=="VisA"
            assert result["image_sha256"]==case["sha256"]
            reference=expected[case["id"]]
            delta=abs(result["score"]-reference["offline_score"])
            assert delta<=max(.001,.001*abs(reference["offline_score"]))
            assert (result["score"]>result["threshold"])==bool(reference["offline_prediction"])
            assert result["agent_trace"][0]["tool_input"]["category"]==category
            artifacts={}
            decoded_source=cv2.imdecode(np.frombuffer(source.content,np.uint8),cv2.IMREAD_COLOR)
            for key in ("original_url","heatmap_url","overlay_url"):
                asset=client.get(result["assets"][key]);asset.raise_for_status()
                decoded=cv2.imdecode(np.frombuffer(asset.content,np.uint8),cv2.IMREAD_COLOR)
                assert decoded is not None and decoded.shape==decoded_source.shape
                if key=="original_url":assert np.array_equal(decoded,decoded_source)
                artifacts[key]={"http_status":asset.status_code,"sha256":hashlib.sha256(asset.content).hexdigest(),"bytes":len(asset.content),"shape":list(decoded.shape)}
            samples.append({"demo_id":case["id"],"category":category,"request_id":response.headers["x-request-id"],"inspection_id":result["id"],
                            "decision":result["decision"],"score":result["score"],"threshold":result["threshold"],"normal_bank_sha256":result["normal_bank_sha256"],
                            "model_mode":result["model_mode"],"synthetic":False,"offline_score":reference["offline_score"],"score_absolute_delta":delta,
                            "reported_server_runtime_ms":result["runtime_ms"],"observed_client_ms":end_to_end_ms,"artifacts":artifacts})
    output={"utc":datetime.now(timezone.utc).isoformat(),"endpoint":base,"health":health_data,"profiles":profiles,"static_files":static_checks,"samples":samples,
            "note":"Six curated operational smoke cases; not an independent accuracy or latency benchmark. Subtle examples include existing false clears. Original photo pixels are checked exactly after decode."}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(json.dumps({"real_live_inspections":len(samples),"decisions":[r["decision"] for r in samples],"max_score_delta":max(r["score_absolute_delta"] for r in samples),"static_files_verified":len(static_checks)}))


if __name__=="__main__":main()
