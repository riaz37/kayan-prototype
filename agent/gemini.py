"""
LLM agent loop with tool calling (OpenAI-compatible API).
Handles the conversation flow: user message → LLM → tool calls → reply.
Supports primary + fallback models for reliability.
"""
import json
import logging
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
_last_request_time = 0
_MIN_REQUEST_INTERVAL = 0.2  # 200ms between requests = 5 RPM max


def _get_client():
    """Lazy-initialize the OpenAI client pointing to vLLM."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key or "none",
            base_url=settings.llm_base_url + "/v1",
        )
    return _client


def _rate_limit():
    """Enforce minimum interval between API calls."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


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
    """Call LLM with fallback model support."""
    model = model or settings.llm_model
    try:
        _rate_limit()
        return _get_client().chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_OPENAI,
            temperature=0.3,
            max_tokens=1024,
        )
    except Exception as e:
        logger.warning(f"Primary model {model} failed: {e}")
        if model != settings.llm_fallback_model:
            logger.info(f"Trying fallback model: {settings.llm_fallback_model}")
            _rate_limit()
            return _get_client().chat.completions.create(
                model=settings.llm_fallback_model,
                messages=messages,
                tools=TOOLS_OPENAI,
                temperature=0.3,
                max_tokens=1024,
            )
        raise


def _call_llm_stream(messages: list, model: str = None):
    """Call LLM with streaming enabled."""
    model = model or settings.llm_model
    try:
        _rate_limit()
        return _get_client().chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_OPENAI,
            temperature=0.3,
            max_tokens=1024,
            stream=True,
        )
    except Exception as e:
        logger.warning(f"Primary model {model} failed: {e}")
        if model != settings.llm_fallback_model:
            logger.info(f"Trying fallback model: {settings.llm_fallback_model}")
            _rate_limit()
            return _get_client().chat.completions.create(
                model=settings.llm_fallback_model,
                messages=messages,
                tools=TOOLS_OPENAI,
                temperature=0.3,
                max_tokens=1024,
                stream=True,
            )
        raise


def _convert_history(history: list, system_msg: Optional[str] = None) -> list:
    """Convert Gemini-style history to OpenAI message format."""
    messages = []

    if system_msg:
        messages.append({"role": "system", "content": system_msg})

    for msg in history:
        role = msg.get("role", "")
        parts = msg.get("parts", [])

        if role == "user":
            # Check if this is a function_response (tool result)
            for part in parts:
                if isinstance(part, dict) and "function_response" in part:
                    fr = part["function_response"]
                    messages.append({
                        "role": "tool",
                        "tool_call_id": fr.get("name", ""),
                        "content": json.dumps(fr.get("response", {}), ensure_ascii=False),
                    })
                    return  # function_response is always a standalone message

            # Regular user message
            text = " ".join(
                p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p
            )
            if text:
                messages.append({"role": "user", "content": text})

        elif role == "model":
            # Check if this contains function_call (tool call)
            has_tool_call = False
            for part in parts:
                if isinstance(part, dict) and "function_call" in part:
                    has_tool_call = True
                    fc = part["function_call"]
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": f"call_{fc.get('name', 'unknown')}",
                            "type": "function",
                            "function": {
                                "name": fc.get("name", ""),
                                "arguments": json.dumps(fc.get("args", {}), ensure_ascii=False),
                            },
                        }],
                    })

            if not has_tool_call:
                text = " ".join(
                    p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p
                )
                if text:
                    messages.append({"role": "assistant", "content": text})

    return messages


def handle_message(phone: str, user_text: str) -> str:
    """
    Process an incoming user message through the LLM agent loop.
    Returns the agent's Arabic text reply.
    """
    # Track incoming message
    analytics.track_message(phone, is_user=True)
    
    # 1. Load conversation history
    history = sessions.get_history(phone)

    # 2. Add user message
    user_part = {"text": user_text}
    history.append({"role": "user", "parts": [user_part]})
    sessions.add_to_history(phone, "user", [user_part])

    # 3. Build context injection
    context = sessions.get_context(phone)
    context_msg = _build_context_message(phone, context)

    # 4. Convert to OpenAI format
    # Append context to system message instead of wasting a turn
    system_msg = SYSTEM_PROMPT
    if context_msg:
        system_msg = SYSTEM_PROMPT + "\n\n---\n\n## Current Context\n" + context_msg
    messages = _convert_history(history, system_msg=system_msg)

    # 5. Call LLM with tools (loop for tool calls)
    for round_num in range(MAX_TOOL_ROUNDS):
        # Log token count for monitoring
        token_count = _count_message_tokens(messages)
        if token_count > 3000:
            logger.warning(f"High token count: {token_count} (round {round_num})")

        try:
            response = _call_llm(messages)
        except Exception as e:
            logger.error(f"LLM API error (all models failed): {e}")
            return _map_error_to_friendly(str(e))

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message:
            return "عذراً، لم أتمكن من فهم طلبك. يرجى إعادة الصياغة."

        message = choice.message

        # Handle reasoning models (Qwen, DeepSeek) that put thinking in reasoning field
        # If content is None but reasoning exists, use reasoning as the content
        if message.content is None and hasattr(message, 'reasoning') and message.reasoning:
            message.content = message.reasoning

        # Check if response has tool calls
        if message.tool_calls:
            # Add assistant message with tool calls to history
            assistant_msg = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                } for tc in message.tool_calls],
            }
            messages.append(assistant_msg)

            # Execute each tool call
            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")

                # Execute the tool with retry
                tool_result = _execute_tool_with_retry(tool_name, tool_args)
                tool_success = "error" not in tool_result
                analytics.track_tool_call(phone, tool_name, success=tool_success)
                logger.info(f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:300]}")

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

                # Update session context based on tool calls
                _update_session_from_tool(phone, tool_name, tool_args, tool_result)

        else:
            # No tool calls — extract text reply
            reply_text = message.content or ""
            if reply_text:
                sessions.add_to_history(phone, "model", [{"text": reply_text}])
                analytics.track_message(phone, is_user=False)
                return reply_text.strip()
            else:
                analytics.track_message(phone, is_user=False)
                return "عذراً، لم أتمكن من إيجاد إجابة مناسبة."

    # If we exhausted tool rounds
    analytics.track_message(phone, is_user=False)
    return "عذراً، أحتاج خطوات إضافية. يرجى التواصل مع موظف خدمة المستفيدين."


def handle_message_stream(phone: str, user_text: str):
    """
    Process an incoming user message with streaming support.
    Yields partial responses: ('text', chunk), ('tool', tool_name), ('done', full_reply)
    """
    # 1. Load conversation history
    history = sessions.get_history(phone)

    # 2. Add user message
    user_part = {"text": user_text}
    history.append({"role": "user", "parts": [user_part]})
    sessions.add_to_history(phone, "user", [user_part])

    # 3. Build context injection
    context = sessions.get_context(phone)
    context_msg = _build_context_message(phone, context)

    # 4. Convert to OpenAI format
    system_msg = SYSTEM_PROMPT
    if context_msg:
        system_msg = SYSTEM_PROMPT + "\n\n---\n\n## Current Context\n" + context_msg
    messages = _convert_history(history, system_msg=system_msg)

    # 5. Call LLM with tools (loop for tool calls)
    for round_num in range(MAX_TOOL_ROUNDS):
        token_count = _count_message_tokens(messages)
        if token_count > 3000:
            logger.warning(f"High token count: {token_count} (round {round_num})")

        try:
            stream = _call_llm_stream(messages)
        except Exception as e:
            logger.error(f"LLM API error (all models failed): {e}")
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

        # Handle reasoning models
        if full_content == "" and hasattr(stream, 'reasoning') and stream.reasoning:
            full_content = stream.reasoning
            yield ("text", full_content)

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

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

                _update_session_from_tool(phone, tool_name, tool_args, tool_result)
        else:
            # No tool calls — done
            if full_content:
                sessions.add_to_history(phone, "model", [{"text": full_content}])
                yield ("done", full_content.strip())
            else:
                yield ("done", "عذراً، لم أتمكن من إيجاد إجابة مناسبة.")
            return

    # Exhausted tool rounds
    yield ("done", "عذراً، أحتاج خطوات إضافية. يرجى التواصل مع موظف خدمة المستفيدين.")


def _build_context_message(phone: str, context: Optional[dict]) -> str:
    """Build a context injection message from the WhatsApp inbound result."""
    if not context:
        return ""

    if not context.get("known"):
        # Check if we have any collected slots for this unknown user
        collected = sessions.get_session(phone).get("collected_slots", {})
        ctx_parts = [
            f"سياق المحادثة: متصل جديد (غير مسجل في النظام). رقم الجوال: {phone}.",
            "ابدأ بالترحيب واسأل عن أهدافه.",
            f"عند إنشاء تذكرة استخدم phone={phone}.",
        ]
        if collected:
            ctx_parts.append(f"معلومات تم جمعها مسبقاً: {json.dumps(collected, ensure_ascii=False)}")
        return "\n".join(ctx_parts)

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
