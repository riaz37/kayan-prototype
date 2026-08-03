"""
Conversation analytics for the Kayan WhatsApp agent.
Tracks metrics like message counts, tool usage, response times, and error rates.
"""
import time
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory analytics store (reset on restart)
_analytics = {
    "conversations": defaultdict(lambda: {
        "message_count": 0,
        "tool_calls": defaultdict(int),
        "start_time": None,
        "last_activity": None,
        "errors": 0,
        "flows_started": set(),
        "flows_completed": set(),
    }),
    "global": {
        "total_messages": 0,
        "total_tool_calls": defaultdict(int),
        "total_errors": 0,
        "start_time": time.time(),
    },
}


def track_message(phone: str, is_user: bool):
    """Track a message in the conversation."""
    conv = _analytics["conversations"][phone]
    conv["message_count"] += 1
    conv["last_activity"] = time.time()
    if conv["start_time"] is None:
        conv["start_time"] = time.time()
    _analytics["global"]["total_messages"] += 1


def track_tool_call(phone: str, tool_name: str, success: bool = True):
    """Track a tool call."""
    conv = _analytics["conversations"][phone]
    conv["tool_calls"][tool_name] += 1
    _analytics["global"]["total_tool_calls"][tool_name] += 1
    if not success:
        conv["errors"] += 1
        _analytics["global"]["total_errors"] += 1


def track_flow(phone: str, flow_name: str, completed: bool = False):
    """Track a conversation flow (registration, support request, etc.)."""
    conv = _analytics["conversations"][phone]
    conv["flows_started"].add(flow_name)
    if completed:
        conv["flows_completed"].add(flow_name)


def get_conversation_stats(phone: str) -> dict:
    """Get analytics for a specific conversation."""
    conv = _analytics["conversations"][phone]
    duration = (conv["last_activity"] or 0) - (conv["start_time"] or 0)
    return {
        "phone": phone,
        "message_count": conv["message_count"],
        "tool_calls": dict(conv["tool_calls"]),
        "errors": conv["errors"],
        "duration_seconds": round(duration, 1),
        "flows_started": list(conv["flows_started"]),
        "flows_completed": list(conv["flows_completed"]),
    }


def get_global_stats() -> dict:
    """Get global analytics across all conversations."""
    uptime = time.time() - _analytics["global"]["start_time"]
    return {
        "total_messages": _analytics["global"]["total_messages"],
        "total_tool_calls": dict(_analytics["global"]["total_tool_calls"]),
        "total_errors": _analytics["global"]["total_errors"],
        "unique_conversations": len(_analytics["conversations"]),
        "uptime_seconds": round(uptime, 1),
    }


def get_top_tools(limit: int = 10) -> list:
    """Get the most used tools across all conversations."""
    tool_counts = _analytics["global"]["total_tool_calls"]
    sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"tool": t, "count": c} for t, c in sorted_tools[:limit]]


def get_error_rate() -> float:
    """Get the error rate across all conversations."""
    total = _analytics["global"]["total_messages"]
    errors = _analytics["global"]["total_errors"]
    if total == 0:
        return 0.0
    return round(errors / total, 4)
