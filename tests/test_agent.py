"""
Agent session and message-assembly behaviour.

The bug these pin down: only plain-text turns were persisted, so on the next
message the model could not see which tools had run. It would then announce
"تم إنشاء ملفكم برقم BEN-1001" without ever having called create_file.

None of these need a live LLM.
"""
import json
import os
import tempfile

import pytest


@pytest.fixture
def sessions(monkeypatch):
    """A sessions module bound to a throwaway database."""
    import importlib
    from agent import sessions as module

    tmp = tempfile.mkdtemp(prefix="kayan-agent-")
    monkeypatch.setattr(module, "DB_DIR", tmp)
    monkeypatch.setattr(module, "DB_PATH", os.path.join(tmp, "sessions.db"))
    monkeypatch.setattr(module, "_conn", None)
    yield module
    module._conn = None
    importlib.reload(module)


def test_tool_calls_survive_to_the_next_turn(sessions):
    phone = "966500000001"
    sessions.append_message(phone, {"role": "user", "content": "ابغى اسجل"})
    sessions.append_messages(phone, [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "create_file", "arguments": '{"city":"الرياض"}'}}]},
        {"role": "tool", "tool_call_id": "call_1",
         "content": json.dumps({"beneficiary_id": "BEN-2001"}, ensure_ascii=False)},
        {"role": "assistant", "content": "تم إنشاء ملفكم"},
    ])

    history = sessions.get_history(phone)
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert history[1]["tool_calls"][0]["function"]["name"] == "create_file"
    assert "BEN-2001" in history[2]["content"]


def test_legacy_gemini_style_history_is_upgraded(sessions):
    """Existing sessions.db files hold {"role": "model", "parts": [...]} rows."""
    phone = "966500000002"
    sess = sessions.get_session(phone)
    sess["history"] = [
        {"role": "user", "parts": [{"text": "مرحبا"}]},
        {"role": "model", "parts": [{"text": "اهلا بكم"}]},
    ]
    sessions._save_session(phone, sess)

    history = sessions.get_history(phone)
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["content"] == "اهلا بكم"


def test_trim_never_orphans_a_tool_result(sessions):
    """A `tool` message with no preceding assistant tool_calls is rejected by
    the API, so trimming must cut at a user turn."""
    long_text = "ب" * 6000
    history = []
    for _ in range(6):
        history += [
            {"role": "user", "content": long_text},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c", "type": "function",
                 "function": {"name": "get_completeness", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c", "content": long_text},
            {"role": "assistant", "content": "تم"},
        ]

    trimmed = sessions._trim_history(history)
    assert len(trimmed) < len(history), "history should actually be trimmed"
    assert trimmed[0]["role"] == "user"
    for i, msg in enumerate(trimmed):
        if msg["role"] == "tool":
            assert trimmed[i - 1].get("tool_calls"), "tool result lost its call"


def test_build_messages_strips_bookkeeping_keys():
    from agent.llm import _build_messages

    messages = _build_messages(
        [{"role": "user", "content": "مرحبا", "at": "2026-08-04T10:00:00Z"}],
        "SYSTEM")
    assert messages[0] == {"role": "system", "content": "SYSTEM"}
    # `at` is ours, not part of the chat API schema
    assert messages[1] == {"role": "user", "content": "مرحبا"}


def test_sampling_disables_thinking_by_default():
    from agent.llm import _sampling

    kwargs = _sampling()
    extra = kwargs["extra_body"]
    assert extra["chat_template_kwargs"]["enable_thinking"] is False
    assert extra["top_k"] == 20
    assert kwargs["tool_choice"] == "auto"


def test_prompt_forbids_unverified_confirmations():
    from agent.prompts import SYSTEM_PROMPT

    assert "TOOL DISCIPLINE" in SYSTEM_PROMPT
    assert "Never invent an ID" in SYSTEM_PROMPT


def test_every_declared_tool_has_a_handler():
    from agent.tools import TOOLS_OPENAI, TOOL_HANDLERS

    declared = {t["function"]["name"] for t in TOOLS_OPENAI}
    assert declared == set(TOOL_HANDLERS), "declared tools and handlers disagree"


def test_unknown_tool_returns_an_error_not_an_exception():
    from agent.tools import execute_tool

    assert "error" in execute_tool("no_such_tool", {})


def test_webhook_message_extraction():
    from agent.whatsapp import extract_message

    payload = {"entry": [{"changes": [{"value": {
        "contacts": [{"profile": {"name": "سعد"}}],
        "messages": [{"from": "966500000003", "id": "wamid.1", "type": "text",
                      "text": {"body": "مرحبا"}}]}}]}]}
    msg = extract_message(payload)
    assert msg["from"] == "966500000003"
    assert msg["text"] == "مرحبا"
    assert msg["contact_name"] == "سعد"

    # a delivery-status callback carries no message
    assert extract_message({"entry": [{"changes": [{"value": {"statuses": []}}]}]}) is None


# ---------------------------------------------------------------- SSE endpoint
@pytest.fixture
def agent_client(monkeypatch):
    from fastapi.testclient import TestClient
    from agent import main as agent_main

    monkeypatch.setattr(agent_main, "_load_context", lambda *a, **k: None)
    return TestClient(agent_main.app), agent_main


def _events(response):
    out = []
    for line in response.text.splitlines():
        if line.startswith("data:"):
            out.append(json.loads(line[5:]))
    return out


def test_chat_streams_sse_by_default(agent_client, monkeypatch):
    client, agent_main = agent_client

    def fake_stream(phone, text):
        yield ("text", "وعليكم ")
        yield ("text", "السلام")
        yield ("done", "وعليكم السلام")

    monkeypatch.setattr(agent_main.agent, "handle_message_stream", fake_stream)
    r = client.post("/agent/chat", json={"from_number": "966500000010", "text_ar": "مرحبا"})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events(r)
    assert [e["type"] for e in events] == ["delta", "delta", "done"]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "وعليكم السلام"
    assert events[-1]["reply"] == "وعليكم السلام"


def test_chat_emits_tool_and_reset_events(agent_client, monkeypatch):
    """Preamble written before a tool call must be retractable — otherwise the
    console shows the model's throat-clearing as if it were the answer."""
    client, agent_main = agent_client

    def fake_stream(phone, text):
        yield ("text", "دعني أتحقق")
        yield ("reset", None)
        yield ("tool", "check_phone")
        yield ("text", "الرقم غير مسجل")
        yield ("done", "الرقم غير مسجل")

    monkeypatch.setattr(agent_main.agent, "handle_message_stream", fake_stream)
    events = _events(client.post("/agent/chat",
                                 json={"from_number": "966500000011", "text_ar": "سجلني"}))

    assert [e["type"] for e in events] == ["delta", "reset", "tool", "delta", "done"]
    assert events[2]["name"] == "check_phone"
    assert events[-1]["reply"] == "الرقم غير مسجل"


def test_chat_stream_false_returns_the_original_json(agent_client, monkeypatch):
    """Scripts and the WhatsApp path still need one blocking response."""
    client, agent_main = agent_client
    monkeypatch.setattr(agent_main.agent, "handle_message", lambda p, t: "رد كامل")

    r = client.post("/agent/chat?stream=false",
                    json={"from_number": "966500000012", "text_ar": "مرحبا"})
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["reply"] == "رد كامل"


def test_chat_stream_reports_errors_as_an_event(agent_client, monkeypatch):
    client, agent_main = agent_client

    def boom(phone, text):
        yield ("text", "…")
        raise RuntimeError("llm exploded")

    monkeypatch.setattr(agent_main.agent, "handle_message_stream", boom)
    events = _events(client.post("/agent/chat",
                                 json={"from_number": "966500000013", "text_ar": "مرحبا"}))
    assert events[-1]["type"] == "error"
    # apologises in the user's language rather than leaking the traceback
    assert "عذرا" in events[-1]["message"].replace("ً", "")


def test_error_reply_matches_the_users_language():
    from agent.main import _error_reply

    assert "عذرا" in _error_reply("مرحبا").replace("ً", "")
    assert _error_reply("hello").startswith("Sorry")
