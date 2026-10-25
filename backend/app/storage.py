from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import ASSET_DIR, DB_PATH, DATA_DIR


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS inspections (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, inspection_id TEXT NOT NULL, decision TEXT NOT NULL, note TEXT, reviewed_at TEXT NOT NULL, FOREIGN KEY(inspection_id) REFERENCES inspections(id))")
        con.execute("CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, created_at TEXT NOT NULL)")


def cleanup_expired(retention_days: int = 30) -> int:
    """Delete local inspection records and generated image artifacts after retention."""
    initialize()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, retention_days))).isoformat()
    with connect() as con:
        expired = [row["id"] for row in con.execute("SELECT id FROM inspections WHERE created_at < ?", (cutoff,)).fetchall()]
        expired_artifacts = [row["id"] for row in con.execute("SELECT id FROM artifacts WHERE created_at < ?", (cutoff,)).fetchall()]
        for inspection_id in expired:
            con.execute("DELETE FROM reviews WHERE inspection_id=?", (inspection_id,))
            con.execute("DELETE FROM inspections WHERE id=?", (inspection_id,))
        for artifact_id in expired_artifacts:
            con.execute("DELETE FROM artifacts WHERE id=?", (artifact_id,))
    for artifact_id in [*expired, *expired_artifacts]:
        for asset in ASSET_DIR.glob(f"{artifact_id}_*.png"):
            asset.unlink(missing_ok=True)
    return len(expired) + len(expired_artifacts)


def register_artifact(artifact_id: str, created_at: str | None = None) -> None:
    initialize()
    with connect() as con:
        con.execute(
            "INSERT INTO artifacts(id, created_at) VALUES(?,?)",
            (artifact_id, created_at or datetime.now(timezone.utc).isoformat()),
        )


def save_inspection(inspection_id: str, payload: dict) -> None:
    with connect() as con:
        con.execute("INSERT INTO inspections(id, created_at, payload) VALUES(?,?,?)", (inspection_id, payload["created_at"], json.dumps(payload, separators=(",", ":"))))


def get_inspection(inspection_id: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT payload FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload"])
        reviews = con.execute("SELECT decision,note,reviewed_at FROM reviews WHERE inspection_id=? ORDER BY id", (inspection_id,)).fetchall()
    payload["reviews"] = [dict(r) for r in reviews]
    payload["reviewer"] = payload["reviews"][-1] if payload["reviews"] else None
    return payload


def append_review(inspection_id: str, decision: str, note: str | None) -> dict | None:
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        exists = con.execute("SELECT 1 FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if not exists:
            return None
        con.execute("INSERT INTO reviews(inspection_id,decision,note,reviewed_at) VALUES(?,?,?,?)", (inspection_id, decision, note, reviewed_at))
    return {"decision": decision, "note": note, "reviewed_at": reviewed_at}


def list_inspections(limit: int = 20) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT payload FROM inspections ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall()
    return [{"id": p["id"], "created_at": p["created_at"], "decision": p["decision"], "score": p["score"], "synthetic": p["synthetic"], "class_name": p.get("class_name", "synthetic_machined_plate")} for p in (json.loads(r["payload"]) for r in rows)]
