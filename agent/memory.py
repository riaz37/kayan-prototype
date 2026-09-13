"""
Long-term memory: per-phone conversation summaries embedded into a vector store.
Persists across session timeouts (unlike sessions.py's rolling history window),
so the agent can recall facts from past conversations with a beneficiary.
"""
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

import httpx
import sqlite_vec
from openai import OpenAI

from agent.config import settings

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "memory.db")

EMBEDDING_DIM = 1024
SEARCH_OVERFETCH = 20  # KNN candidates fetched before filtering by phone
TOP_K = 3
MIN_SIMILARITY = 0.5  # 1 / (1 + L2 distance); below this, treat as irrelevant

_conn = None
_llm_client = None


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _get_conn():
    global _conn
    if _conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.enable_load_extension(True)
        sqlite_vec.load(_conn)
        _conn.enable_load_extension(False)
        _init_tables()
    return _conn


def _init_tables():
    conn = _conn
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(
            embedding float[{EMBEDDING_DIM}]
        )
    """)
    conn.commit()


def _get_llm_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            api_key=settings.llm_api_key or "none",
            base_url=settings.llm_base_url + "/v1",
        )
    return _llm_client


def _embed(text: str) -> list[float]:
    resp = httpx.post(
        f"{settings.embedding_base_url}/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={"model": settings.embedding_model, "input": text},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def _transcript(history: list[dict]) -> str:
    lines = []
    for msg in history:
        role = "User" if msg.get("role") == "user" else "Agent"
        for part in msg.get("parts", []):
            text = (part.get("text") or "").strip()
            if text:
                lines.append(f"{role}: {text}")
    return "\n".join(lines)[-6000:]


def _summarize(history: list[dict]) -> Optional[str]:
    transcript = _transcript(history)
    if not transcript:
        return None
    try:
        resp = _get_llm_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": (
                    "Summarize this WhatsApp support conversation in 1-3 short sentences. "
                    "Capture the beneficiary's name/identity if mentioned, their issue or "
                    "request, and how it was resolved or left off. Write in English "
                    "regardless of the conversation's language. Be factual and concise."
                )},
                {"role": "user", "content": transcript},
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        message = resp.choices[0].message
        content = message.content
        if not content and hasattr(message, "reasoning") and message.reasoning:
            content = message.reasoning
        summary = (content or "").strip()
        return summary or None
    except Exception as e:
        logger.warning(f"Memory summarization failed: {e}")
        return None


def save_memory(phone: str, history: list[dict]) -> Optional[str]:
    """Summarize a finished conversation and store it as a searchable memory."""
    summary = _summarize(history)
    if not summary:
        return None

    try:
        embedding = _embed(summary)
    except Exception as e:
        logger.warning(f"Memory embedding failed: {e}")
        return None

    conn = _get_conn()
    now = _now_iso()
    cur = conn.execute(
        "INSERT INTO memories (phone, summary, created_at) VALUES (?, ?, ?)",
        (phone, summary, now),
    )
    memory_id = cur.lastrowid
    conn.execute(
        "INSERT INTO vec_memories (rowid, embedding) VALUES (?, ?)",
        (memory_id, sqlite_vec.serialize_float32(embedding)),
    )
    conn.commit()
    logger.info(f"Saved memory for {phone}: {summary[:100]}")
    return summary


def search_memories(phone: str, query: str, top_k: int = TOP_K) -> list[dict]:
    """Find past-conversation memories for this phone relevant to the query."""
    try:
        query_embedding = _embed(query)
    except Exception as e:
        logger.warning(f"Memory search embedding failed: {e}")
        return []

    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT m.phone, m.summary, m.created_at, v.distance
        FROM vec_memories v
        JOIN memories m ON m.id = v.rowid
        WHERE v.embedding MATCH ? AND k = ?
        ORDER BY v.distance
        """,
        (sqlite_vec.serialize_float32(query_embedding), SEARCH_OVERFETCH),
    ).fetchall()

    results = []
    for row_phone, summary, created_at, distance in rows:
        if row_phone != phone:
            continue
        similarity = 1 / (1 + distance)
        if similarity < MIN_SIMILARITY:
            continue
        results.append({"summary": summary, "created_at": created_at, "similarity": similarity})
        if len(results) >= top_k:
            break
    return results


def list_memories(phone: str, limit: int = 20) -> list[dict]:
    """List stored memories for a phone, most recent first (for debugging)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT summary, created_at FROM memories WHERE phone = ? ORDER BY created_at DESC LIMIT ?",
        (phone, limit),
    ).fetchall()
    return [{"summary": r[0], "created_at": r[1]} for r in rows]
