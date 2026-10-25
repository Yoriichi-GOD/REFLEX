from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import logging
import os
from pathlib import Path
import secrets
import subprocess
import time
import uuid
from collections import defaultdict, deque

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent.controller import run_policy
from app.config import APP_VERSION, ASSET_DIR, DATA_DIR, MODEL_DIR, ROOT
from app.core.alignment import align_affine, compare_aligned
from app.core.image_io import ImageInputError, decode_image, image_mime, sha256_bytes
from app.core.model import fit_normal_bank, render_evidence
from app.core.engine import analyze, load_bank
from app import storage
from app import profiles as model_profiles

logging.basicConfig(level=logging.INFO, format="%(message)s")


def _bootstrap_local_assets() -> None:
    if (MODEL_DIR / "patch_bank.npz").exists() or (MODEL_DIR / "normal_bank.npz").exists():
        return
    if not (DATA_DIR / "synthetic" / "train_normal").exists():
        from scripts.make_fixtures import build
        build()
    if not (MODEL_DIR / "normal_bank.npz").exists() and not (MODEL_DIR / "patch_bank.npz").exists():
        data = DATA_DIR / "synthetic"
        fit_normal_bank(sorted((data / "train_normal").glob("*.png")), sorted((data / "calibration_normal").glob("*.png")), MODEL_DIR, source="synthetic")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if int(cv2.__version__.split(".")[0]) != 5:
        raise RuntimeError(f"REFLEX requires OpenCV 5.x, found {cv2.__version__}. Install backend/requirements.txt; OpenCV 4 is not supported.")
    _bootstrap_local_assets()
    storage.initialize()
    storage.cleanup_expired(int(os.getenv("INSPECTION_RETENTION_DAYS", "30")))
    for directory in model_profiles.directories(MODEL_DIR).values():
        load_bank(directory)
    cleanup_task = asyncio.create_task(_cleanup_periodically())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


async def _cleanup_periodically() -> None:
    retention_days = max(1, int(os.getenv("INSPECTION_RETENTION_DAYS", "30")))
    interval_seconds = max(60, int(os.getenv("INSPECTION_CLEANUP_INTERVAL_SECONDS", "3600")))
    logger = logging.getLogger("reflex.retention")
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            expired_count = await asyncio.to_thread(storage.cleanup_expired, retention_days)
            if expired_count:
                logger.info(json.dumps({"event": "expired_records_removed", "count": expired_count, "retention_days": retention_days}, separators=(",", ":")))
        except Exception:
            logger.exception("REFLEX retention cleanup failed")


app = FastAPI(title="REFLEX inspection service", version=APP_VERSION, lifespan=lifespan)
_UPLOADS_BY_CLIENT: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def upload_rate_limit(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500
    is_upload = request.method == "POST" and (request.url.path == "/api/inspections" or request.url.path.endswith("/continue") or request.url.path == "/api/align")
    try:
        response = None
        if is_upload:
            key = request.client.host if request.client else "unknown"
            now = time.monotonic()
            recent = _UPLOADS_BY_CLIENT[key]
            window_seconds = int(os.getenv("UPLOAD_RATE_WINDOW_SECONDS", "600"))
            maximum = int(os.getenv("UPLOADS_PER_WINDOW", "10"))
            while recent and now - recent[0] >= window_seconds:
                recent.popleft()
            if len(recent) >= maximum:
                response = JSONResponse(status_code=429, content={"detail": {"code": "UPLOAD_RATE_LIMITED", "message": "Upload limit reached. Try again after the short cooling period."}}, headers={"Retry-After": str(window_seconds)})
            else:
                recent.append(now)
        if response is None:
            response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Reflex-Server-Ms"] = str(round((time.perf_counter()-started)*1000,3))
        if os.getenv("REFLEX_BENCHMARK_MODE")=="1":
            response.headers["X-Reflex-Process-ID"] = str(os.getpid())
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "/unmatched")
        logging.getLogger("reflex.request").info(json.dumps({
            "event": "request_completed", "request_id": request_id,
            "method": request.method, "route": route_path,
            "status_code": status_code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }, separators=(",", ":")))


class ReviewRequest(BaseModel):
    decision: str
    note: str | None = Field(default=None, max_length=1000)


def _build_revision() -> str:
    if os.getenv("BUILD_COMMIT"):
        return os.environ["BUILD_COMMIT"]
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True, timeout=2).strip()
    except Exception:
        return "working-tree"


def _demo_hashes() -> set[str]:
    cases_path = ROOT / "demo" / "cases.json"
    if not cases_path.exists():
        return set()
    return {str(case.get("sha256")) for case in json.loads(cases_path.read_text(encoding="utf-8"))}


def _validate_upload_mime(claimed: str | None, raw: bytes) -> None:
    try:
        detected = image_mime(raw)
    except ImageInputError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    supplied = (claimed or "application/octet-stream").split(";", 1)[0].strip().lower()
    if supplied not in {"application/octet-stream", "image/png", "image/jpeg", "image/webp"} or (supplied != "application/octet-stream" and supplied != detected):
        raise HTTPException(status_code=415, detail={"code": "MIME_MISMATCH", "message": "The file type does not match its PNG, JPEG, or WebP content."})


def _write_asset(name: str, image: np.ndarray) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / name
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Could not write artifact {name}")


def _profile_directory(category: str | None = None) -> Path:
    try:
        return model_profiles.resolve(category, MODEL_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "CATEGORY_UNSUPPORTED", "message": "Select an available inspection profile."}) from exc


def _real_demo_cases() -> list[dict]:
    path = ROOT / "demo" / "real" / "cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"] if path.exists() else []


def _inspect_bytes(raw: bytes, category: str, continuation_of: str | None = None, extra_trace: list[dict] | None = None, request_id: str | None = None) -> dict:
    started = time.perf_counter()
    try:
        image, source_meta = decode_image(raw)
    except ImageInputError as exc:
        raise HTTPException(status_code=413 if exc.code == "UPLOAD_TOO_LARGE" else 400, detail={"code": exc.code, "message": str(exc)}) from exc
    decode_ms=(time.perf_counter()-started)*1000
    profile_started=time.perf_counter()
    model_directory = _profile_directory(category)
    mean, scale, model_meta = load_bank(model_directory)
    profile_load_ms=(time.perf_counter()-profile_started)*1000
    expected_category = model_meta.get("category", "synthetic_machined_plate")
    if category != expected_category:
        raise HTTPException(status_code=422, detail={"code": "CATEGORY_UNSUPPORTED", "message": f"The active model profile is {expected_category}; select that category."})
    vision = analyze(image, mean, scale, model_meta)
    source_hash = sha256_bytes(raw)
    synthetic = source_hash in _demo_hashes()
    policy_started=time.perf_counter()
    agent = run_policy(image, vision, mean, scale, synthetic_example=synthetic)
    policy_ms=(time.perf_counter()-policy_started)*1000
    artifacts_started=time.perf_counter()
    inspection_id = str(uuid.uuid4())
    asset_names = {key: f"{inspection_id}_{suffix}.png" for key, suffix in (("original", "original"), ("heatmap", "heatmap"), ("overlay", "overlay"), ("mask", "mask"))}
    heat, overlay, _ = render_evidence(image, vision["score_map"], vision["pixel_threshold"])
    if vision["model_mode"] == "opencv_dnn_patch_memory":
        mask = np.where(vision["score_map"] > vision["pixel_threshold"], 255, 0).astype(np.uint8)
    else:
        mask_small = np.where(vision["small_score_map"] > vision["pixel_threshold"], 255, 0).astype(np.uint8)
        mask = cv2.resize(mask_small, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    _write_asset(asset_names["original"], image)
    _write_asset(asset_names["heatmap"], heat)
    _write_asset(asset_names["overlay"], overlay)
    _write_asset(asset_names["mask"], mask)
    if agent.get("crop_evidence"):
        x1, y1, x2, y2 = agent["crop_evidence"]["source_bbox_xyxy"]
        roi_name = f"{inspection_id}_roi.png"
        _write_asset(roi_name, image[y1:y2, x1:x2])
        asset_names["roi"] = roi_name
    model_manifest_hash = hashlib.sha256((model_directory / "metadata.json").read_bytes()).hexdigest()
    real_demo = next((case for case in _real_demo_cases() if case["sha256"] == source_hash and case["category"] == category), None)
    trace = (extra_trace or []) + agent["agent_trace"]
    for index, entry in enumerate(trace, start=1):
        entry["step"] = index
    regions = []
    for index, region in enumerate(vision["regions"], start=1):
        regions.append({"id": f"region-{index}", **region, "evidence_ids": [trace[0]["tool_result_id"]]})
    runtime_ms = round((time.perf_counter() - started) * 1000, 3)
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": inspection_id, "status": "needs_input" if agent["agent_status"] == "needs_input" else "done",
        "created_at": now, "image_sha256": source_hash, "source_dimensions": source_meta,
        "class_name": category, "model_version": vision["model_version"], "model_mode": vision["model_mode"],
        "model_manifest_sha256": model_manifest_hash, "normal_bank_sha256": vision["normal_bank_sha256"],
        "cv_version": cv2.__version__, "build_revision": _build_revision(), "runtime_ms": runtime_ms,
        "score": round(float(vision["score"]), 6), "threshold": round(float(vision["threshold"]), 6),
        "pass_threshold": round(float(vision["pass_threshold"]),6) if "pass_threshold" in vision else None,
        "stage_timings": {**vision.get("stage_timings",{}),"decode_validate_ms":decode_ms,"profile_load_ms":profile_load_ms,
                          "agent_policy_ms":policy_ms,"detail_inspection_ms":vision.get("second_look",{}).get("elapsed_ms",0.) if vision.get("second_look") else 0.,
                          "artifacts_and_payload_ms":(time.perf_counter()-artifacts_started)*1000},
        "runtime_scope": "Decode through artifact/payload creation; full handler/serialization in X-Reflex-Server-Ms header and request log",
        "second_look_is_additional_camera_view": False,
        "disposition_reason": trace[-1].get("decision_reason_code"),
        "pixel_threshold": round(float(vision["pixel_threshold"]), 6), "score_type": vision.get("score_type", "normalized_feature_distance"),
        "calibrated_probability": False, "score_margin": round(float(vision["score_margin"]), 4),
        "decision": agent["decision"], "decision_text": agent["decision_text"], "quality": vision["quality"],
        "foreground_bbox_xyxy": vision["foreground_bbox_xyxy"], "regions": regions,
        "agent_trace": trace, "agent_status": agent["agent_status"], "needs_action": agent["needs_action"],
        "crop_evidence": agent.get("crop_evidence"),
        "assets": {f"{key}_url": f"/assets/{name}" for key, name in asset_names.items()},
        "synthetic": synthetic, "data_source": "REFLEX seeded synthetic fixtures" if synthetic else ("VisA real benchmark photograph" if real_demo else "user-provided image; ownership not asserted"),
        "demo_attribution": real_demo.get("attribution") if real_demo else None,
        "previous_inspection_id": continuation_of, "reviews": [], "reviewer": None,
        "threshold_provenance": {
            "method": model_meta["calibration_method"], "normal_calibration_count": model_meta["calibration_count"],
            "synthetic_calibration": model_meta["synthetic"], "image_threshold": model_meta["image_threshold"],
            "pixel_threshold_method": model_meta["pixel_threshold_method"],
            "pass_threshold": model_meta.get("pass_threshold"),
            "review_development": model_meta.get("review_development"),
        },
    }
    storage.save_inspection(inspection_id, payload)
    logging.getLogger("reflex.inspection").info(json.dumps({
        "event": "inspection_completed", "request_id": request_id, "inspection_id": inspection_id,
        "opencv_version": cv2.__version__,
        "model_mode": vision["model_mode"], "decision": agent["decision"],
        "score": round(float(vision["score"]), 6), "threshold": round(float(vision["threshold"]), 6),
        "agent_tools": [entry["selected_tool"] for entry in trace], "runtime_ms": runtime_ms,
        "image_sha256": source_hash,"model_version":vision["model_version"],"normal_bank_sha256":vision["normal_bank_sha256"],
        "stage_timings":payload["stage_timings"],
        "synthetic": synthetic,
    }, separators=(",", ":")))
    return payload


@app.get("/api/health")
async def health():
    try:
        options = model_profiles.directories(MODEL_DIR)
        directory = _profile_directory()
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        model_ready = all((p / ("patch_bank.npz" if json.loads((p / "metadata.json").read_text(encoding="utf-8")).get("model_mode") == "opencv_dnn_patch_memory" else "normal_bank.npz")).exists() for p in options.values())
    except Exception:
        metadata, model_ready = {}, False
    return {
        "status": "ok" if model_ready and int(cv2.__version__.split(".")[0]) == 5 else "not_ready",
        "app_version": APP_VERSION, "opencv_version": cv2.__version__, "model_ready": model_ready,
        "model_mode": metadata.get("model_mode"), "build_revision": _build_revision(),
        "runtime": os.getenv("REFLEX_RUNTIME", "aws" if os.getenv("AWS_EXECUTION_ENV") else "local"),
        "renderer": "opencv-python-headless", "uptime_seconds": round(time.monotonic() - _STARTED, 3),
    }


@app.get("/api/ready")
async def ready():
    health_data = await health()
    if health_data["status"] != "ok":
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_READY", "message": "OpenCV 5 normal bank is not ready."})
    return {"status": "ready", "opencv_version": health_data["opencv_version"], "model_mode": health_data["model_mode"]}


_STARTED = time.monotonic()


@app.get("/api/profiles")
async def profiles():
    available = []
    selected = _profile_directory()
    for category, directory in model_profiles.directories(MODEL_DIR).items():
        _, _, metadata = load_bank(directory)
        source = metadata.get("data_source", "local normal images")
        display_name = "Synthetic machined plate" if category == "synthetic_machined_plate" else f"{source.split(':')[0]} · {category}"
        available.append({"category": category, "display_name": display_name, "data_source": source, "model_version": metadata["model_version"], "model_mode": metadata["model_mode"], "threshold": metadata["image_threshold"], "threshold_type": "normal-calibrated anomaly score", "training_count": metadata["training_count"], "calibration_count": metadata["calibration_count"], "synthetic": metadata["synthetic"], "default": directory == selected})
    return {"profiles": available}


@app.get("/api/demo-cases")
async def demo_cases(category: str | None = None):
    _, _, metadata = load_bank(_profile_directory(category))
    if metadata.get("synthetic") is not True:
        return {"cases": [case for case in _real_demo_cases() if case["category"] == metadata["category"]], "dataset": "VisA", "synthetic": False}
    path = ROOT / "demo" / "cases.json"
    if not path.exists():
        return {"cases": []}
    return {"cases": json.loads(path.read_text(encoding="utf-8"))}


@app.get("/api/inspections")
async def inspections(limit: int = 20):
    return {"inspections": storage.list_inspections(limit)}


@app.post("/api/inspections")
async def create_inspection(request: Request, file: UploadFile = File(...), category: str = Form("synthetic_machined_plate")):
    raw = await file.read(12 * 1024 * 1024 + 1)
    _validate_upload_mime(file.content_type, raw)
    return _inspect_bytes(raw, category, request_id=request.state.request_id)


@app.get("/api/inspections/{inspection_id}")
async def get_inspection(inspection_id: str):
    result = storage.get_inspection(inspection_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection does not exist."})
    return result


@app.post("/api/inspections/{inspection_id}/continue")
async def continue_inspection(request: Request, inspection_id: str, file: UploadFile = File(...)):
    parent = storage.get_inspection(inspection_id)
    if parent is None:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection does not exist."})
    if not parent.get("needs_action") or parent["needs_action"].get("type") != "new_capture":
        raise HTTPException(status_code=409, detail={"code": "AGENT_ACTION_NOT_AVAILABLE", "message": "This inspection has no open new-capture request."})
    raw = await file.read(12 * 1024 * 1024 + 1)
    _validate_upload_mime(file.content_type, raw)
    prior_trace = list(parent["agent_trace"])
    child = _inspect_bytes(raw, parent["class_name"], continuation_of=inspection_id, extra_trace=prior_trace, request_id=request.state.request_id)
    return child


@app.post("/api/inspections/{inspection_id}/review")
async def review(inspection_id: str, payload: ReviewRequest, x_review_token: str | None = Header(default=None)):
    allowed = {"confirm_defect", "override_acceptable", "request_retake"}
    if payload.decision not in allowed:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REVIEW_DECISION", "message": f"Choose one of {sorted(allowed)}."})
    expected = os.getenv("REFLEX_REVIEW_TOKEN")
    if expected and (not x_review_token or not secrets.compare_digest(expected, x_review_token)):
        raise HTTPException(status_code=401, detail={"code": "REVIEW_UNAUTHORIZED", "message": "Reviewer token required."})
    item = storage.append_review(inspection_id, payload.decision, payload.note)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection does not exist."})
    return {"inspection_id": inspection_id, "reviewer": item, "model_decision_unchanged": True}


@app.get("/api/inspections/{inspection_id}/export")
async def export(inspection_id: str, format: str = "json"):
    result = storage.get_inspection(inspection_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection does not exist."})
    if format == "json":
        name = f"reflex-{inspection_id}.json"
        return Response(json.dumps(result, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{name}"'})
    if format != "html":
        raise HTTPException(status_code=422, detail={"code": "INVALID_EXPORT_FORMAT", "message": "Use format=json or format=html."})
    safe_json = html.escape(json.dumps(result, indent=2))
    body = f"""<!doctype html><html><head><meta charset=utf-8><title>REFLEX report {html.escape(inspection_id)}</title><style>body{{font:15px system-ui;max-width:960px;margin:40px auto;padding:0 24px;color:#172536}}img{{max-width:100%}}pre{{white-space:pre-wrap;background:#f3f5f7;padding:18px}}</style></head><body><h1>REFLEX inspection report</h1><p>{html.escape(result['decision_text'])}</p><img src="{html.escape(result['assets']['overlay_url'])}" alt="OpenCV anomaly overlay"><pre>{safe_json}</pre></body></html>"""
    return HTMLResponse(body, headers={"Content-Disposition": f'attachment; filename="reflex-{inspection_id}.html"'})


@app.post("/api/align")
async def align_pair(reference: UploadFile = File(...), candidate: UploadFile = File(...)):
    ref_bytes, candidate_bytes = await reference.read(12 * 1024 * 1024 + 1), await candidate.read(12 * 1024 * 1024 + 1)
    _validate_upload_mime(reference.content_type, ref_bytes)
    _validate_upload_mime(candidate.content_type, candidate_bytes)
    try:
        ref, _ = decode_image(ref_bytes)
        new, _ = decode_image(candidate_bytes)
    except ImageInputError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    aligned, evidence = align_affine(ref, new)
    if aligned is None:
        return {"alignment": evidence, "comparison": None, "accepted": False}
    difference, comparison = compare_aligned(ref, aligned)
    artifact_id = str(uuid.uuid4())
    storage.register_artifact(artifact_id)
    _write_asset(f"{artifact_id}_aligned.png", aligned)
    _write_asset(f"{artifact_id}_difference.png", difference)
    return {"alignment": evidence, "comparison": comparison, "accepted": True, "aligned_url": f"/assets/{artifact_id}_aligned.png", "difference_url": f"/assets/{artifact_id}_difference.png", "reference_sha256": sha256_bytes(ref_bytes), "candidate_sha256": sha256_bytes(candidate_bytes)}


@app.get("/api/evaluations/latest")
async def latest_evaluation(category: str | None = None):
    directory = _profile_directory(category)
    _, _, metadata = load_bank(directory)
    if metadata.get("synthetic") is not True:
        if metadata.get("model_mode") == "opencv_dnn_patch_memory":
            evaluation_directory = os.getenv("REFLEX_EVALUATION_DIR")
            path = Path(evaluation_directory) / f"{metadata['category']}.json" if evaluation_directory else directory.parent.parent / metadata["category"] / "metrics.json"
            if path.exists():
                measured = json.loads(path.read_text(encoding="utf-8"))
                if measured.get("model_sha256") == metadata.get("normal_bank_sha256"):
                    image, pixel = measured["image_metrics"], measured["pixel_metrics"]
                    return {"dataset": f"VisA · {metadata['category']}", "run_id": "improvement_20261024", "synthetic": False,
                            "metrics": {"sample_count": image["sample_count"], "image_auroc": round(image["auroc"], 4),
                                        "f1_at_threshold": round(image["f1"], 4), "pixel_iou": round(pixel["pixel_iou_at_frozen_normal_threshold"], 4)},
                            "interpretation": "Reused official test split after baseline diagnosis; thresholds from separate normal calibration only. Accuracy measured offline; this demo computes each upload live."}
        return {"status": "not_evaluated", "message": "No matching evaluation artifact is available for the active real-image model."}
    files = list((ROOT / "results").glob("eval_*.json"))
    if not files:
        return {"status": "not_evaluated", "message": "Run `make evaluate` to generate the synthetic holdout evaluation."}
    latest = max(files, key=lambda path: path.stat().st_mtime)
    return json.loads(latest.read_text(encoding="utf-8"))


@app.exception_handler(Exception)
async def unexpected_error(_request, exc: Exception):
    # Keep server details out of browser responses; structured server logs retain the exception.
    logging.getLogger("reflex").exception("Unhandled REFLEX request error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "Inspection failed. Check the service log using the inspection request time."}})


app.mount("/assets", StaticFiles(directory=ASSET_DIR, check_dir=False), name="assets")
app.mount("/demo/samples", StaticFiles(directory=ROOT / "demo" / "samples", check_dir=False), name="demo-samples")
app.mount("/demo/real", StaticFiles(directory=ROOT / "demo" / "real", check_dir=False), name="real-demo-images")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True, check_dir=False), name="frontend")
