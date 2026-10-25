"""Exercise a running local profile; this small smoke is not a latency benchmark."""
from __future__ import annotations
import csv
from datetime import datetime,timezone
import json
from pathlib import Path

import cv2
import httpx
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"reports"/"improvement_20261024"
DATA=ROOT.parent/"reflex-data"/"visa"/"prepared"


def main():
    with (OUT/"candle"/"per_case.csv").open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    normal=next(r for r in rows if r["label"]=="0" and r["prediction"]=="0")
    defect=max((r for r in rows if r["label"]=="1"),key=lambda r:float(r["score"]))
    c=httpx.Client(base_url="http://127.0.0.1:8001",timeout=60)
    health=c.get("/api/health");assert health.status_code==200 and health.json()["model_mode"]=="opencv_dnn_patch_memory"
    evaluation=c.get("/api/evaluations/latest");assert evaluation.status_code==200 and evaluation.json()["synthetic"] is False
    samples=[]
    def post(raw,name,category="candle",url="/api/inspections"):
        response=c.post(url,data={"category":category},files={"file":(name,raw,"image/jpeg")})
        return response
    for selected,expected in ((normal,"PASS"),(defect,"DEFECT_FOUND")):
        part="bad" if selected["label"]=="1" else "good"
        path=DATA/"candle"/"test"/part/Path(selected["case_id"]).name
        response=post(path.read_bytes(),path.name);assert response.status_code==200
        result=response.json();assert result["decision"]==expected
        assert abs(result["score"]-float(selected["score"]))<1e-6
        artifacts={}
        for key in ("original_url","heatmap_url","overlay_url","mask_url"):
            asset=c.get(result["assets"][key]);assert asset.status_code==200
            image=cv2.imdecode(np.frombuffer(asset.content,np.uint8),cv2.IMREAD_UNCHANGED)
            assert image is not None and image.shape[:2]==(result["source_dimensions"]["height"],result["source_dimensions"]["width"])
            artifacts[key]={"http_status":asset.status_code,"shape":list(image.shape)}
        samples.append({"case_id":selected["case_id"],"inspection_id":result["id"],"decision":result["decision"],"score":result["score"],"benchmark_score_match":True,"artifacts":artifacts})
    train=next((DATA/"candle"/"train"/"good").glob("*.JPG"));source=cv2.imread(str(train))
    blurred=cv2.GaussianBlur(source,(81,81),20);ok,encoded=cv2.imencode(".jpg",blurred);assert ok
    response=post(encoded.tobytes(),"blurred.jpg");assert response.status_code==200
    low=response.json();assert low["decision"]=="NEEDS_REVIEW" and low["needs_action"]["type"]=="new_capture"
    continued=post(train.read_bytes(),train.name,url=f"/api/inspections/{low['id']}/continue")
    assert continued.status_code==200 and continued.json()["previous_inspection_id"]==low["id"]
    wrong=post(train.read_bytes(),train.name,category="cashew");assert wrong.status_code==422
    corrupt=post(b"not an image","corrupt.jpg");assert corrupt.status_code==400
    result={"utc":datetime.now(timezone.utc).isoformat(),"runtime":"local","health":health.json(),"matching_evaluation":evaluation.json(),
            "samples":samples,"blurred_capture":{"decision":low["decision"],"quality_flags":low["quality"]["flags"]},
            "continuation":{"status":continued.status_code,"decision":continued.json()["decision"],"parent_link_verified":True},
            "wrong_category_status":wrong.status_code,"corrupt_upload_status":corrupt.status_code,
            "note":"Small functional smoke; selected examples are not an independent accuracy or performance benchmark."}
    (OUT/"local_smoke.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"decisions":[r["decision"] for r in samples],"blurred":low["decision"],"continuation":continued.json()["decision"],"wrong_category":wrong.status_code,"corrupt":corrupt.status_code}))


if __name__=="__main__":main()
