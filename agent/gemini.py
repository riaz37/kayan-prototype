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

logger = logging.getLogger(__name__)

_client = None

MAX_TOOL_ROUNDS = 10

# Rate limiting
_last_request_time = 0
_MIN_REQUEST_INTERVAL = 0.2  # 200ms between requests = 5 RPM max


def _get_client():
    """Lazy-initialize the OpenAI client pointing to Gemini API."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key or "none",
            base_url=settings.llm_base_url,
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
            max_tokens=4096,
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
                max_tokens=4096,
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
    messages = _convert_history(history, system_msg=SYSTEM_PROMPT)

    # Insert context at the beginning (after system message)
    if context_msg:
        messages.insert(1, {"role": "user", "content": context_msg})
        messages.insert(2, {"role": "assistant", "content": "تم استلام السياق. جاهز للخدمة."})

    # 5. Call LLM with tools (loop for tool calls)
    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            response = _call_llm(messages)
        except Exception as e:
            logger.error(f"LLM API error (all models failed): {e}")
            return "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى."

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

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)
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
                return reply_text.strip()
            else:
                return "عذراً، لم أتمكن من إيجاد إجابة مناسبة."

    # If we exhausted tool rounds
    return "عذراً، أحتاج خطوات إضافية. يرجى التواصل مع موظف خدمة المستفيدين."


def _build_context_message(phone: str, context: Optional[dict]) -> str:
    """Build a context injection message from the WhatsApp inbound result."""
    if not context:
        return ""

    if not context.get("known"):
        return (
            "سياق المحادثة: متصل جديد (غير مسجل في النظام). "
            "ابدأ بالترحيب واسأل عن أهدافه."
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
