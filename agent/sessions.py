"""
SQLite-backed conversation session store.
Per-phone conversation history + context for the Gemini agent.
Persists across server restarts.
"""
import json
import os
import sqlite3
from typing import Optional
from datetime import datetime, timedelta

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "sessions.db")

SESSION_TIMEOUT = timedelta(minutes=30)
MAX_HISTORY = 50

_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_table()
    return _conn


def _init_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            phone TEXT PRIMARY KEY,
            history TEXT DEFAULT '[]',
            context TEXT,
            beneficiary_id TEXT,
            current_flow TEXT,
            collected_slots TEXT DEFAULT '{}',
            last_active TEXT,
            created_at TEXT
        )
    """)
    conn.commit()


def _now() -> datetime:
    return datetime.utcnow()


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat() + "Z"


def get_session(phone: str) -> dict:
    """Get or create a session for a phone number."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE phone = ?", (phone,)).fetchone()

    if row:
        last_active = datetime.fromisoformat(row["last_active"].replace("Z", ""))
        sess = {
            "phone": phone,
            "history": json.loads(row["history"] or "[]"),
            "context": json.loads(row["context"]) if row["context"] else None,
            "beneficiary_id": row["beneficiary_id"],
            "current_flow": row["current_flow"],
            "collected_slots": json.loads(row["collected_slots"] or "{}"),
            "last_active": last_active,
        }
        # Mark inactive if timeout exceeded, but keep history
        if (_now() - last_active) > SESSION_TIMEOUT:
            sess["context"] = None
            sess["current_flow"] = None
            sess["collected_slots"] = {}
        return sess

    # Create new session
    now = _now_iso()
    sess = {
        "phone": phone,
        "history": [],
        "context": None,
        "beneficiary_id": None,
        "current_flow": None,
        "collected_slots": {},
        "last_active": _now(),
    }
    conn.execute(
        "INSERT INTO sessions (phone, history, context, beneficiary_id, current_flow, collected_slots, last_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (phone, "[]", None, None, None, "{}", now, now),
    )
    conn.commit()
    return sess


def _save_session(phone: str, sess: dict):
    """Persist session to SQLite."""
    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET history = ?, context = ?, beneficiary_id = ?, current_flow = ?, collected_slots = ?, last_active = ? WHERE phone = ?",
        (
            json.dumps(sess["history"], ensure_ascii=False),
            json.dumps(sess["context"], ensure_ascii=False) if sess["context"] else None,
            sess["beneficiary_id"],
            sess["current_flow"],
            json.dumps(sess["collected_slots"], ensure_ascii=False),
            _now_iso(),
            phone,
        ),
    )
    conn.commit()


def get_history(phone: str) -> list[dict]:
    """Get Gemini-formatted conversation history for a phone."""
    sess = get_session(phone)
    return sess["history"][-MAX_HISTORY:]


def add_to_history(phone: str, role: str, parts: list[dict]):
    """Append a message to conversation history."""
    sess = get_session(phone)
    sess["history"].append({"role": role, "parts": parts})
    sess["last_active"] = _now()
    _save_session(phone, sess)


def set_context(phone: str, context: dict):
    """Set the beneficiary context from /whatsapp/inbound."""
    sess = get_session(phone)
    sess["context"] = context
    if context and context.get("known"):
        sess["beneficiary_id"] = context.get("beneficiary_id")
    sess["last_active"] = _now()
    _save_session(phone, sess)


def get_context(phone: str) -> Optional[dict]:
    """Get the current beneficiary context."""
    sess = get_session(phone)
    return sess.get("context")


def set_flow(phone: str, flow: str):
    """Set the current agent flow (intake, file_completion, etc.)."""
    sess = get_session(phone)
    sess["current_flow"] = flow
    sess["collected_slots"] = {}
    sess["last_active"] = _now()
    _save_session(phone, sess)


def get_flow(phone: str) -> Optional[str]:
    """Get the current agent flow."""
    return get_session(phone).get("current_flow")


def set_slot(phone: str, key: str, value):
    """Store a collected slot value."""
    sess = get_session(phone)
    sess.setdefault("collected_slots", {})[key] = value
    sess["last_active"] = _now()
    _save_session(phone, sess)


def get_slot(phone: str, key: str):
    """Get a collected slot value."""
    return get_session(phone).get("collected_slots", {}).get(key)


def clear_session(phone: str):
    """Clear a session (for restart or timeout)."""
    conn = _get_conn()
    conn.execute("DELETE FROM sessions WHERE phone = ?", (phone,))
    conn.commit()


def get_all_sessions() -> list[dict]:
    """Get all active sessions (for debugging)."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM sessions ORDER BY last_active DESC").fetchall()
    return [
        {
            "phone": r["phone"],
            "beneficiary_id": r["beneficiary_id"],
            "current_flow": r["current_flow"],
            "history_count": len(json.loads(r["history"] or "[]")),
            "last_active": r["last_active"],
        }
        for r in rows
    ]
