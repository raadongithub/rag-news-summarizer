import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("DB_PATH", "/data/sessions.db"))


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id                      TEXT PRIMARY KEY,
                url                     TEXT,
                article_json            TEXT,
                summary                 TEXT,
                chat_history_json       TEXT NOT NULL DEFAULT '[]',
                retrieved_passages_json TEXT,
                status                  TEXT NOT NULL DEFAULT 'idle',
                error_message           TEXT,
                created_at              TEXT NOT NULL,
                updated_at              TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["chat_history"] = json.loads(d.pop("chat_history_json") or "[]")
    d["article"] = json.loads(d["article_json"]) if d.get("article_json") else None
    d.pop("article_json", None)
    d["retrieved_passages"] = (
        json.loads(d["retrieved_passages_json"])
        if d.get("retrieved_passages_json")
        else None
    )
    d.pop("retrieved_passages_json", None)
    return d


def create_session() -> dict:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, chat_history_json, status, created_at, updated_at) VALUES (?, '[]', 'idle', ?, ?)",
            (session_id, now, now),
        )
        conn.commit()
    return get_session(session_id)


def get_session(session_id: str) -> Optional[dict]:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return _row_to_dict(row)


def update_session(session_id: str, **fields: Any) -> Optional[dict]:
    if not fields:
        return get_session(session_id)

    now = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now

    # Serialize complex fields to JSON
    if "chat_history" in fields:
        fields["chat_history_json"] = json.dumps(fields.pop("chat_history"))
    if "article" in fields:
        fields["article_json"] = json.dumps(fields.pop("article"))
    if "retrieved_passages" in fields:
        fields["retrieved_passages_json"] = json.dumps(fields.pop("retrieved_passages"))

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [session_id]

    with _get_connection() as conn:
        conn.execute(f"UPDATE sessions SET {set_clause} WHERE id = ?", values)
        conn.commit()

    return get_session(session_id)
