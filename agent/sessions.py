"""
SQLite-backed conversation session store.
Per-phone conversation history + context for the LLM agent.
Persists across server restarts.
"""
import json
import os
import sqlite3
from typing import Optional
from datetime import datetime, timedelta, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "sessions.db")

SESSION_TIMEOUT = timedelta(minutes=30)
MAX_HISTORY = 50
MAX_HISTORY_TOKENS = 8000  # ~32K chars / 4 chars per token
MIN_HISTORY_KEEP = 20  # Always keep last 20 messages

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
    """Naive UTC, matching the backend's timestamp convention."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat() + "Z"


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _trim_history(history: list) -> list:
    """Trim history to stay within token limits while keeping recent messages.

    Cuts only at a `user` message. An assistant message carrying tool_calls and
    the `tool` messages answering it must stay together — starting a request
    with an orphaned tool result is rejected by the API.
    """
    if not history:
        return history

    total_tokens = sum(
        _estimate_tokens(json.dumps(msg, ensure_ascii=False))
        for msg in history
    )
    if total_tokens <= MAX_HISTORY_TOKENS:
        return history

    cut = max(0, len(history) - MIN_HISTORY_KEEP)
    while cut < len(history) and history[cut].get("role") != "user":
        cut += 1
    return history[cut:] if cut < len(history) else history[-MIN_HISTORY_KEEP:]


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


def _as_openai(entry: dict) -> dict:
    """Accept both the current OpenAI-shaped entries and the legacy
    Gemini-style {"role": "user"|"model", "parts": [{"text": ...}]} rows that
    older sessions.db files contain."""
    if "parts" not in entry:
        return entry
    text = " ".join(p.get("text", "") for p in entry.get("parts", [])
                    if isinstance(p, dict) and p.get("text"))
    role = "assistant" if entry.get("role") == "model" else "user"
    return {"role": role, "content": text, "at": entry.get("at")}


def get_history(phone: str) -> list[dict]:
    """Conversation history as OpenAI messages, trimmed to fit token limits."""
    sess = get_session(phone)
    history = [_as_openai(m) for m in sess["history"][-MAX_HISTORY:]]
    return _trim_history(history)


def append_message(phone: str, message: dict):
    """Append one OpenAI-format message to the conversation.

    Tool calls and tool results are stored too. Previously only the plain text
    turns were kept, so on the next message the model could no longer see which
    tools had actually run — and would happily announce "your file has been
    created" without ever having called create_file.
    """
    sess = get_session(phone)
    sess["history"].append({**message, "at": _now_iso()})
    sess["last_active"] = _now()
    _save_session(phone, sess)


def append_messages(phone: str, messages: list[dict]):
    if not messages:
        return
    sess = get_session(phone)
    stamp = _now_iso()
    for m in messages:
        sess["history"].append({**m, "at": stamp})
    sess["last_active"] = _now()
    _save_session(phone, sess)


def add_to_history(phone: str, role: str, parts: list[dict]):
    """Legacy helper kept for older callers (demo/test scripts)."""
    text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text"))
    append_message(phone, {"role": "assistant" if role == "model" else role, "content": text})


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


def clear_all_sessions():
    """Clear all sessions."""
    conn = _get_conn()
    conn.execute("DELETE FROM sessions")
    conn.commit()
    return True


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
