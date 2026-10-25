from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload an owned synthetic fixture and verify live OpenCV evidence.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--expect-aws", action="store_true")
    parser.add_argument("--proof-file", type=Path)
    args = parser.parse_args()
    path = ROOT / "demo" / "samples" / "scratch.png"
    if not path.exists():
        raise SystemExit("Demo sample missing; run `make demo-data` first.")
    raw = path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    with httpx.Client(base_url=args.api_base.rstrip("/"), timeout=45) as client:
        health = client.get("/api/health"); health.raise_for_status()
        health_data = health.json()
        if not health_data.get("opencv_version", "").startswith("5."):
            raise SystemExit(f"Expected OpenCV 5, got {health_data.get('opencv_version')}")
        if args.expect_aws and health_data.get("runtime") != "aws":
            raise SystemExit("The API health response does not identify an AWS runtime.")
        response = client.post("/api/inspections", files={"file": ("synthetic-scratch.png", raw, "image/png"), "category": (None, "synthetic_machined_plate")})
        response.raise_for_status(); result = response.json()
        if result["image_sha256"] != source_hash:
            raise SystemExit("Source hash mismatch in the inspection response.")
        if not any(t["selected_tool"] == "inspect_crop" for t in result["agent_trace"]):
            raise SystemExit("The synthetic defect did not trigger a native crop inspection.")
        overlay = client.get(result["assets"]["overlay_url"]); overlay.raise_for_status()
        if not overlay.content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise SystemExit("Annotated output is missing or not a PNG.")
        proof = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": args.api_base.rstrip("/"),
            "request_id": response.headers.get("x-request-id"),
            "inspection_id": result["id"],
            "opencv_version": health_data["opencv_version"],
            "runtime": health_data["runtime"],
            "build_revision": health_data["build_revision"],
            "decision": result["decision"],
            "score": result["score"],
            "threshold": result["threshold"],
            "tool_trace": [entry["selected_tool"] for entry in result["agent_trace"]],
            "source_sha256": source_hash,
            "overlay_sha256": hashlib.sha256(overlay.content).hexdigest(),
            "overlay_bytes": len(overlay.content),
            "synthetic_fixture": True,
        }
        if not proof["request_id"]:
            raise SystemExit("The response is missing its request correlation ID.")
        if args.proof_file:
            args.proof_file.parent.mkdir(parents=True, exist_ok=True)
            args.proof_file.write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(f"health: OpenCV {health_data['opencv_version']} | runtime {health_data['runtime']} | build {health_data['build_revision']}")
        print(f"request: {proof['request_id']}")
        print(f"inspection: {result['id']} | decision {result['decision']} | score {result['score']:.6f} vs threshold {result['threshold']:.6f}")
        print(f"source sha256: {source_hash}")
        print(f"overlay sha256: {hashlib.sha256(overlay.content).hexdigest()} | bytes {len(overlay.content)}")
        # Use a Windows-console-safe separator so smoke output works under the
        # default CP1252 encoding as well as UTF-8 terminals.
        print("trace: " + " -> ".join(t["selected_tool"] for t in result["agent_trace"]))
        if args.proof_file:
            print(f"proof: {args.proof_file}")


if __name__ == "__main__":
    main()
