"""
In-memory conversation session store.
Per-phone conversation history + context for the Gemini agent.
"""
from typing import Optional
from datetime import datetime, timedelta

# phone -> session data
_sessions: dict[str, dict] = {}

SESSION_TIMEOUT = timedelta(minutes=30)
MAX_HISTORY = 20


def _now() -> datetime:
    return datetime.utcnow()


def get_session(phone: str) -> dict:
    """Get or create a session for a phone number."""
    if phone in _sessions:
        sess = _sessions[phone]
        last = sess.get("last_active")
        if last and (_now() - last) > SESSION_TIMEOUT:
            sess["history"] = []
            sess["context"] = None
            sess["current_flow"] = None
            sess["collected_slots"] = {}
        sess["last_active"] = _now()
        return sess
    sess = {
        "phone": phone,
        "history": [],
        "context": None,
        "beneficiary_id": None,
        "current_flow": None,
        "collected_slots": {},
        "last_active": _now(),
    }
    _sessions[phone] = sess
    return sess


def get_history(phone: str) -> list[dict]:
    """Get Gemini-formatted conversation history for a phone."""
    sess = get_session(phone)
    return sess["history"][-MAX_HISTORY:]


def add_to_history(phone: str, role: str, parts: list[dict]):
    """Append a message to conversation history."""
    sess = get_session(phone)
    sess["history"].append({"role": role, "parts": parts})
    sess["last_active"] = _now()


def set_context(phone: str, context: dict):
    """Set the beneficiary context from /whatsapp/inbound."""
    sess = get_session(phone)
    sess["context"] = context
    if context and context.get("known"):
        sess["beneficiary_id"] = context.get("beneficiary_id")
    sess["last_active"] = _now()


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


def get_flow(phone: str) -> Optional[str]:
    """Get the current agent flow."""
    return get_session(phone).get("current_flow")


def set_slot(phone: str, key: str, value):
    """Store a collected slot value."""
    sess = get_session(phone)
    sess.setdefault("collected_slots", {})[key] = value
    sess["last_active"] = _now()


def get_slot(phone: str, key: str):
    """Get a collected slot value."""
    return get_session(phone).get("collected_slots", {}).get(key)


def clear_session(phone: str):
    """Clear a session (for restart or timeout)."""
    _sessions.pop(phone, None)
