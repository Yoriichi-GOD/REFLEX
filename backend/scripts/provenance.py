from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "no-commit"


created_at = datetime.now(timezone.utc)
run_id = created_at.strftime("%Y%m%dT%H%M%S%fZ")
files = [ROOT / "backend" / "requirements.txt", ROOT / "data" / "model" / "normal_bank.npz", ROOT / "data" / "model" / "metadata.json", ROOT / "data" / "assets_manifest.json", ROOT / "demo" / "cases.json"]
hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.exists()}
manifest = {"run_id": run_id, "created_at": created_at.isoformat(), "git_revision": git_revision(), "python": platform.python_version(), "platform": platform.platform(), "opencv": cv2.__version__, "numpy": np.__version__, "files_sha256": hashes}
output_path = ROOT / "results" / f"provenance_{run_id}.json"
output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Wrote {output_path.relative_to(ROOT).as_posix()}")
print(json.dumps(manifest, indent=2))
