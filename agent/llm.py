"""
LLM agent loop with tool calling (OpenAI-compatible API).
Handles the conversation flow: user message → LLM → tool calls → reply.

Targets a self-hosted vLLM (Qwen3.6-27B-FP8) by default; any OpenAI-compatible
endpoint works via LLM_BASE_URL / LLM_MODEL.
"""
import json
import logging
import threading
import time
from typing import Optional
from openai import OpenAI

from agent.config import settings
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS_OPENAI, execute_tool
from agent import sessions
from agent import analytics

logger = logging.getLogger(__name__)

_client = None

MAX_TOOL_ROUNDS = 10
MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds

# Rate limiting
_last_request_time = 0.0
_rate_lock = threading.Lock()
_MIN_REQUEST_INTERVAL = 0.2  # 200ms between requests


def _get_client():
    """Lazy-initialize the OpenAI-compatible client."""
    global _client
    if _client is None:
        base = settings.llm_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        _client = OpenAI(api_key=settings.llm_api_key or "none", base_url=base,
                         timeout=settings.llm_timeout_seconds)
    return _client


def _rate_limit():
    """Enforce a minimum interval between API calls (thread-safe)."""
    global _last_request_time
    with _rate_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()


def _sampling(stream=False):
    """Request parameters shared by the streaming and blocking paths."""
    kwargs = {
        "tools": TOOLS_OPENAI,
        "tool_choice": "auto",
        "temperature": settings.llm_temperature,
        "top_p": settings.llm_top_p,
        "max_tokens": settings.llm_max_tokens,
        # top_k is not an OpenAI-standard field; vLLM takes it via extra_body.
        "extra_body": {
            "top_k": settings.llm_top_k,
            "chat_template_kwargs": {"enable_thinking": settings.llm_enable_thinking},
        },
    }
    if stream:
        kwargs["stream"] = True
    return kwargs


def _execute_tool_with_retry(tool_name: str, tool_args: dict) -> dict:
    """Execute tool with retry for transient errors (network, timeout)."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return execute_tool(tool_name, tool_args)
        except Exception as e:
            error_str = str(e).lower()
            # Only retry on transient errors (connection, timeout)
            is_transient = any(kw in error_str for kw in ["connection", "timeout", "network", "reset"])
            if is_transient and attempt < MAX_RETRIES:
                logger.warning(f"Tool {tool_name} transient error (attempt {attempt + 1}): {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            # Non-transient or exhausted retries
            return {"error": str(e)}


# User-friendly error messages for common backend errors
ERROR_MESSAGES = {
    "404": "الخدمة غير متوفرة حاليًا. يرجى المحاولة لاحقًا.",
    "500": "حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
    "502": "الخدمة غير متوفرة حاليًا. يرجى المحاولة لاحقًا.",
    "503": "الخدمة مزدحمة. يرجى المحاولة بعد قليل.",
    "timeout": "استغرق الطلب وقتًا طويلًا. يرجى المحاولة مرة أخرى.",
}


def _map_error_to_friendly(error: str) -> str:
    """Map backend errors to user-friendly Arabic messages."""
    for code, msg in ERROR_MESSAGES.items():
        if code in error:
            return msg
    return "عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى."


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _count_message_tokens(messages: list) -> int:
    """Estimate total tokens in message list."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if content:
            total += _estimate_tokens(content)
        # Also count tool call arguments
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            args = tc.get("function", {}).get("arguments", "")
            total += _estimate_tokens(args)
    return total


def _call_llm(messages: list, model: str = None):
    """Call the LLM, falling back to the secondary model if one is configured."""
    model = model or settings.llm_model
    try:
        _rate_limit()
        return _get_client().chat.completions.create(
            model=model, messages=messages, **_sampling())
    except Exception as e:
        logger.warning(f"Model {model} failed: {e}")
        if settings.llm_fallback_model and model != settings.llm_fallback_model:
            logger.info(f"Trying fallback model: {settings.llm_fallback_model}")
            _rate_limit()
            return _get_client().chat.completions.create(
                model=settings.llm_fallback_model, messages=messages, **_sampling())
        raise


def _call_llm_stream(messages: list, model: str = None):
    """Call the LLM with streaming enabled."""
    model = model or settings.llm_model
    try:
        _rate_limit()
        return _get_client().chat.completions.create(
            model=model, messages=messages, **_sampling(stream=True))
    except Exception as e:
        logger.warning(f"Model {model} failed: {e}")
        if settings.llm_fallback_model and model != settings.llm_fallback_model:
            logger.info(f"Trying fallback model: {settings.llm_fallback_model}")
            _rate_limit()
            return _get_client().chat.completions.create(
                model=settings.llm_fallback_model, messages=messages, **_sampling(stream=True))
        raise


def _build_messages(history: list, system_msg: str) -> list:
    """Prepend the system prompt to the stored conversation.

    History is already in OpenAI shape (sessions._as_openai upgrades any legacy
    rows), so this only strips bookkeeping keys the API does not accept.
    """
    messages = [{"role": "system", "content": system_msg}]
    for msg in history:
        clean = {k: v for k, v in msg.items() if k in
                 ("role", "content", "tool_calls", "tool_call_id", "name")}
        if clean.get("role"):
            messages.append(clean)
    return messages


def handle_message(phone: str, user_text: str) -> str:
    """
    Process an incoming user message through the LLM agent loop.
    Returns the agent's Arabic text reply.
    """
    analytics.track_message(phone, is_user=True)

    # 1. Load history and append the new user turn
    history = sessions.get_history(phone)
    user_msg = {"role": "user", "content": user_text}
    history.append(user_msg)
    sessions.append_message(phone, user_msg)

    # 2. Context goes on the system message rather than burning a turn
    context_msg = _build_context_message(phone, sessions.get_context(phone))
    system_msg = SYSTEM_PROMPT
    if context_msg:
        system_msg = SYSTEM_PROMPT + "\n\n---\n\n## Current Context\n" + context_msg
    messages = _build_messages(history, system_msg)

    # Everything produced this turn is written back to the session at the end,
    # so the next turn can see which tools actually ran and what they returned.
    turn: list[dict] = []

    for round_num in range(MAX_TOOL_ROUNDS):
        token_count = _count_message_tokens(messages)
        if token_count > 3000:
            logger.warning(f"High token count: {token_count} (round {round_num})")

        try:
            response = _call_llm(messages)
        except Exception as e:
            logger.error(f"LLM API error (all models failed): {e}")
            sessions.append_messages(phone, turn)
            return _map_error_to_friendly(str(e))

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message:
            sessions.append_messages(phone, turn)
            return "عذراً، لم أتمكن من فهم طلبك. يرجى إعادة الصياغة."

        message = choice.message

        # This model returns its chain of thought in `reasoning`, separate from
        # the answer in `content`. Never promote reasoning into the reply — it
        # is internal deliberation, not something to send a beneficiary.
        reasoning = getattr(message, "reasoning", None)
        if reasoning and not message.content:
            logger.info(f"Model reasoning (not sent): {str(reasoning)[:300]}")

        if message.tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name,
                                 "arguments": tc.function.arguments},
                } for tc in message.tool_calls],
            }
            messages.append(assistant_msg)
            turn.append(assistant_msg)

            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")
                tool_result = _execute_tool_with_retry(tool_name, tool_args)
                analytics.track_tool_call(phone, tool_name, success="error" not in tool_result)
                logger.info(f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:300]}")

                tool_msg = {"role": "tool", "tool_call_id": tc.id,
                            "content": json.dumps(tool_result, ensure_ascii=False)}
                messages.append(tool_msg)
                turn.append(tool_msg)

                _update_session_from_tool(phone, tool_name, tool_args, tool_result)

        else:
            reply_text = (message.content or "").strip()
            if not reply_text:
                reply_text = "عذراً، لم أتمكن من إيجاد إجابة مناسبة."
            turn.append({"role": "assistant", "content": reply_text})
            sessions.append_messages(phone, turn)
            analytics.track_message(phone, is_user=False)
            return reply_text

    # If we exhausted tool rounds
    sessions.append_messages(phone, turn)
    analytics.track_message(phone, is_user=False)
    return "عذراً، أحتاج خطوات إضافية. يرجى التواصل مع موظف خدمة المستفيدين."


def handle_message_stream(phone: str, user_text: str):
    """
    Process an incoming user message with streaming support.
    Yields partial responses: ('text', chunk), ('tool', tool_name), ('done', full_reply)
    """
    history = sessions.get_history(phone)
    user_msg = {"role": "user", "content": user_text}
    history.append(user_msg)
    sessions.append_message(phone, user_msg)

    context_msg = _build_context_message(phone, sessions.get_context(phone))
    system_msg = SYSTEM_PROMPT
    if context_msg:
        system_msg = SYSTEM_PROMPT + "\n\n---\n\n## Current Context\n" + context_msg
    messages = _build_messages(history, system_msg)

    turn: list[dict] = []

    for round_num in range(MAX_TOOL_ROUNDS):
        token_count = _count_message_tokens(messages)
        if token_count > 3000:
            logger.warning(f"High token count: {token_count} (round {round_num})")

        try:
            stream = _call_llm_stream(messages)
        except Exception as e:
            logger.error(f"LLM API error (all models failed): {e}")
            sessions.append_messages(phone, turn)
            yield ("text", _map_error_to_friendly(str(e)))
            return

        # Process streaming response
        full_content = ""
        tool_calls_data = {}
        
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # Accumulate content
            if delta.content:
                full_content += delta.content
                yield ("text", delta.content)

            # Accumulate tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc.id:
                        tool_calls_data[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_data[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_data[idx]["arguments"] += tc.function.arguments

            # If done, break
            if finish_reason == "stop" or finish_reason == "tool_calls":
                break

        # Check if we have tool calls
        if tool_calls_data:
            # Build assistant message
            assistant_msg = {
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": [{
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                } for tc in tool_calls_data.values()],
            }
            messages.append(assistant_msg)
            turn.append(assistant_msg)

            # Execute each tool call
            for tc in tool_calls_data.values():
                tool_name = tc["name"]
                yield ("tool", tool_name)

                try:
                    tool_args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")
                tool_result = _execute_tool_with_retry(tool_name, tool_args)
                logger.info(f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:300]}")

                tool_msg = {"role": "tool", "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False)}
                messages.append(tool_msg)
                turn.append(tool_msg)

                _update_session_from_tool(phone, tool_name, tool_args, tool_result)
        else:
            reply = (full_content or "").strip() or "عذراً، لم أتمكن من إيجاد إجابة مناسبة."
            turn.append({"role": "assistant", "content": reply})
            sessions.append_messages(phone, turn)
            yield ("done", reply)
            return

    # Exhausted tool rounds
    sessions.append_messages(phone, turn)
    yield ("done", "عذراً، أحتاج خطوات إضافية. يرجى التواصل مع موظف خدمة المستفيدين.")


def _build_context_message(phone: str, context: Optional[dict]) -> str:
    """Build a context injection message from the WhatsApp inbound result."""
    if not context:
        return ""

    if not context.get("known"):
        return (
            f"سياق المحادثة: متصل جديد (غير مسجل في النظام). رقم الجوال: {phone}. "
            "ابدأ بالترحيب واسأل عن أهدافه. "
            f"عند إنشاء تذكرة استخدم phone={phone}."
        )

    beneficiary_id = context.get("beneficiary_id", "")
    name = context.get("name_ar", "")
    file_no = context.get("file_no", "")
    status = context.get("file_status", "")
    pct = context.get("completion_pct", 0)
    missing_docs = context.get("missing_documents", [])
    open_requests = context.get("open_requests", [])
    open_tickets = context.get("open_tickets", [])
    next_disb = context.get("next_disbursement")

    ctx_parts = [
        f"سياق المستفيد: {name} (رقم الملف: {file_no}, beneficiary_id: {beneficiary_id})",
        f"حالة الملف: {status}، الإكمال: {pct}%",
    ]

    if missing_docs:
        ctx_parts.append(f"مستندات ناقصة: {', '.join(missing_docs)}")

    if open_requests:
        reqs = ", ".join([f"{r['id']} ({r['stage']})" for r in open_requests])
        ctx_parts.append(f"طلبات مفتوحة: {reqs}")

    if open_tickets:
        ctx_parts.append(f"تذاكر مفتوحة: {', '.join(open_tickets)}")

    if next_disb:
        ctx_parts.append(
            f"الدفعة القادمة: {next_disb.get('amount_sar', 0)} ريال بتاريخ {next_disb.get('due_date', '')}"
        )

    return "\n".join(ctx_parts)


def _update_session_from_tool(phone: str, tool_name: str, args: dict, result: dict):
    """Update session state based on tool call results."""
    # Track beneficiary_id from create_file or get_file
    if tool_name == "create_file" and result.get("beneficiary_id"):
        sessions.set_slot(phone, "beneficiary_id", result["beneficiary_id"])
        ctx = sessions.get_context(phone) or {}
        ctx["beneficiary_id"] = result["beneficiary_id"]
        ctx["file_no"] = result.get("file_no", "")
        ctx["known"] = True
        sessions.set_context(phone, ctx)

    elif tool_name == "get_file" and result.get("id"):
        sessions.set_slot(phone, "beneficiary_id", result["id"])

    elif tool_name == "check_phone" and result.get("registered"):
        ctx = sessions.get_context(phone) or {}
        ctx["known"] = True
        ctx["beneficiary_id"] = result.get("beneficiary_id", "")
        sessions.set_context(phone, ctx)
