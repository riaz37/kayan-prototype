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
