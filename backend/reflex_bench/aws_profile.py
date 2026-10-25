"""Low-rate synthetic-only public ECS inspection latency profile.

Obeys the deployed service upload guard (10 uploads per 600 seconds) with a
62-second minimum gap. This measures sequential request latency, not saturation
capacity. It uses only exact, hash-registered synthetic demo fixtures.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://re-c0a0c131729f4898bb80d160feb0ccc7.ecs.ap-southeast-2.on.aws"
OUT = ROOT / "reports" / "benchmarks" / "aws_synthetic"
GAP_SECONDS = 62.0
WARMUPS = 10
MEASURED = 100
FIXTURES = [
    ("normal", ROOT / "demo" / "samples" / "normal.png", "f760e95c9ae8efcc5ba3f598896908a0304145d14d35270f896c5648e94b07f2"),
    ("scratch", ROOT / "demo" / "samples" / "scratch.png", "367e54087849c395660dc6abc181b6007b30e78d081889e9b0e13a332504f22d"),
    ("blurred", ROOT / "demo" / "samples" / "blurred.png", "eb83c97e4a18f96bed6253b9dd69fa00434f4bf93f6fd6dc9138cafed8b9e40e"),
]


def _write_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "run_state.tmp"
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(OUT / "run_state.json")
    with (OUT / "requests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(state["attempts"][-1], separators=(",", ":")) + "\n")


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    import numpy as np
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def main() -> None:
    fixture_info = []
    for fixture_id, path, expected_hash in FIXTURES:
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_hash:
            raise RuntimeError(f"Bundled synthetic fixture hash mismatch: {fixture_id}")
        fixture_info.append({"id": fixture_id, "path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": actual, "synthetic": True})
    run_started = datetime.now(timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    state = {"status": "RUNNING", "run_started_utc": run_started, "base_url": BASE_URL,
             "region": "ap-southeast-2", "profile": "synthetic_machined_plate", "fixtures": fixture_info,
             "warmup_target": WARMUPS, "measured_target": MEASURED, "minimum_gap_seconds": GAP_SECONDS,
             "service_upload_limit_per_600_seconds": 10, "concurrency": 1,
             "data_retention_notice": "Application policy says records/uploads are removed after 24 hours; all inputs are bundled synthetic fixtures.",
             "attempts": [], "measured": []}
    _write_state({**state, "attempts": [{"event": "initialization", "time_utc": datetime.now(timezone.utc).isoformat(), "status": "FIXTURE_HASHES_VERIFIED"}]})
    # The health probe is GET-only and does not consume the upload quota.
    health_started = time.perf_counter()
    with httpx.Client(timeout=30.0, headers={"Connection": "close"}) as client:
        health = client.get(f"{BASE_URL}/api/health")
    state["health_probe"] = {"status_code": health.status_code, "latency_ms": (time.perf_counter() - health_started) * 1000,
                             "body": health.json() if "application/json" in health.headers.get("content-type", "") else health.text[:300]}
    if health.status_code != 200:
        state["status"] = "BLOCKED_HEALTH_CHECK"
        state["run_finished_utc"] = datetime.now(timezone.utc).isoformat()
        _write_state({**state, "attempts": [{"event": "health_probe", "time_utc": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED", "status_code": health.status_code}]})
        raise RuntimeError(f"AWS health probe returned HTTP {health.status_code}")
    print(f"HEALTH ok latency_ms={state['health_probe']['latency_ms']:.1f}", flush=True)
    last_attempt_mono: float | None = None
    upload_index = 0
    total_uploads = WARMUPS + MEASURED
    fixture_bytes = {fid: path.read_bytes() for fid, path, _ in FIXTURES}
    request_index = 0
    while request_index < total_uploads:
        phase = "warmup" if request_index < WARMUPS else "measured"
        phase_index = request_index + 1 if phase == "warmup" else request_index - WARMUPS + 1
        fixture_id, path, _ = FIXTURES[request_index % len(FIXTURES)]
        if last_attempt_mono is not None:
            wait = GAP_SECONDS - (time.monotonic() - last_attempt_mono)
            if wait > 0:
                print(f"RATE_GUARD wait_seconds={wait:.1f} next={phase}:{phase_index}", flush=True)
                time.sleep(wait)
        upload_index += 1
        raw = fixture_bytes[fixture_id]
        started = time.perf_counter()
        request_start = datetime.now(timezone.utc).isoformat()
        try:
            with httpx.Client(timeout=90.0, headers={"Connection": "close"}) as client:
                response = client.post(f"{BASE_URL}/api/inspections",
                    data={"category": "synthetic_machined_plate"},
                    files={"file": (path.name, raw, "image/png")})
            elapsed_ms = (time.perf_counter() - started) * 1000
            last_attempt_mono = time.monotonic()
            item = {"request_number": upload_index, "phase": phase, "phase_index": phase_index,
                    "fixture_id": fixture_id, "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                    "request_started_utc": request_start, "status_code": response.status_code,
                    "end_to_end_ms": elapsed_ms, "response_bytes": len(response.content)}
            if response.status_code == 429:
                retry_after = max(600, int(response.headers.get("Retry-After", "600"))) + 5
                item.update({"status": "RATE_LIMITED", "retry_after_seconds": retry_after, "response_excerpt": response.text[:300]})
                state["attempts"].append(item)
                _write_state(state)
                print(f"RATE_LIMITED retry_after={retry_after}s", flush=True)
                time.sleep(retry_after)
                continue
            if response.status_code != 200:
                item.update({"status": "HTTP_ERROR", "response_excerpt": response.text[:500]})
                state["attempts"].append(item)
                state["status"] = "STOPPED_HTTP_ERROR"
                _write_state(state)
                raise RuntimeError(f"Inspection API returned HTTP {response.status_code}; stopped without retry")
            payload = response.json()
            item.update({"status": "OK", "inspection_id": payload.get("id"), "runtime_ms": payload.get("runtime_ms"),
                         "synthetic": payload.get("synthetic"), "data_source": payload.get("data_source"),
                         "decision": payload.get("decision"), "model_version": payload.get("model_version"),
                         "build_revision": payload.get("build_revision")})
            if payload.get("synthetic") is not True or payload.get("data_source") != "REFLEX seeded synthetic fixtures":
                item["status"] = "STOPPED_SYNTHETIC_LABEL_MISMATCH"
                state["attempts"].append(item)
                state["status"] = item["status"]
                _write_state(state)
                raise RuntimeError("Server did not classify the hash-registered demo fixture as synthetic; stopped")
            state["attempts"].append(item)
            if phase == "measured":
                state["measured"].append(item)
            _write_state(state)
            print(f"{phase.upper()} {phase_index}/{WARMUPS if phase == 'warmup' else MEASURED} HTTP={response.status_code} e2e_ms={elapsed_ms:.1f} runtime_ms={payload.get('runtime_ms')} synthetic={payload.get('synthetic')}", flush=True)
            request_index += 1
        except httpx.RequestError as exc:
            item = {"request_number": upload_index, "phase": phase, "phase_index": phase_index,
                    "fixture_id": fixture_id, "request_started_utc": request_start, "status": "TRANSPORT_ERROR_UNCERTAIN",
                    "error": f"{type(exc).__name__}: {exc}"}
            state["attempts"].append(item)
            state["status"] = "STOPPED_TRANSPORT_ERROR_UNCERTAIN"
            _write_state(state)
            raise
    e2e = [float(x["end_to_end_ms"]) for x in state["measured"]]
    runtime = [float(x["runtime_ms"]) for x in state["measured"] if x.get("runtime_ms") is not None]
    def stats(values: list[float]) -> dict:
        return {"n": len(values), "mean_ms": statistics.mean(values) if values else None,
                "stddev_ms": statistics.stdev(values) if len(values) > 1 else (0.0 if values else None),
                "p50_ms": _percentile(values, .50), "p90_ms": _percentile(values, .90),
                "p95_ms": _percentile(values, .95), "max_ms": max(values) if values else None}
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(run_started)).total_seconds()
    state["status"] = "COMPLETED" if len(state["measured"]) == MEASURED else "INCOMPLETE"
    state["run_finished_utc"] = datetime.now(timezone.utc).isoformat()
    state["elapsed_seconds"] = elapsed
    state["measured_stats"] = {"end_to_end_latency": stats(e2e), "server_runtime": stats(runtime),
                               "successful_requests_per_second_over_whole_run": len(e2e) / elapsed if elapsed else None,
                               "note": "Paced single-client sequential profile under the 10/600s guard; throughput is pacing-limited and is not saturation capacity."}
    state["decision_counts"] = {name: sum(x.get("decision") == name for x in state["measured"]) for name in sorted({x.get("decision") for x in state["measured"]})}
    _write_state({**state, "attempts": state["attempts"] + [{"event": "summary", "time_utc": state["run_finished_utc"], "status": state["status"]}]})
    print(json.dumps({"status": state["status"], "warmups": WARMUPS, "measured": len(e2e), "stats": state["measured_stats"], "decision_counts": state["decision_counts"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
