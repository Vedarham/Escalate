"""SQLite persistence for analysis history + uploaded image files."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    image_file TEXT,
    mode TEXT NOT NULL,
    provider TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_module ON analyses(module, created_at);
"""


def _paths() -> tuple[Path, Path]:
    root = get_settings().storage_dir
    uploads = root / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return root / "platform.db", uploads


@contextmanager
def _connect():
    db, _ = _paths()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_image(jpeg: bytes) -> str:
    _, uploads = _paths()
    name = f"{uuid.uuid4().hex}.jpg"
    (uploads / name).write_bytes(jpeg)
    return name


def image_path(name: str) -> Path | None:
    _, uploads = _paths()
    p = (uploads / name).resolve()
    if p.parent != uploads.resolve() or not p.is_file():
        return None
    return p


def record(module: str, title: str, inputs: dict, output: dict, mode: str, provider: str,
           image_file: str | None = None) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO analyses(module, created_at, title, input_json, output_json, image_file, mode, provider)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (module, datetime.now(timezone.utc).isoformat(timespec="seconds"), title[:200],
             json.dumps(inputs, default=str), json.dumps(output, default=str), image_file, mode, provider),
        )
        return int(cur.lastrowid)


def list_records(module: str | None = None, limit: int = 50) -> list[dict]:
    q = "SELECT id, module, created_at, title, image_file, mode, provider FROM analyses"
    args: list = []
    if module:
        q += " WHERE module = ?"
        args.append(module)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute(q, args).fetchall()]


def get_record(record_id: int) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return None
    out = dict(row)
    out["input"] = json.loads(out.pop("input_json"))
    out["output"] = json.loads(out.pop("output_json"))
    return out


def stats() -> dict:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT module, COUNT(*) AS n FROM analyses GROUP BY module").fetchall()
    return {r["module"]: r["n"] for r in rows}
