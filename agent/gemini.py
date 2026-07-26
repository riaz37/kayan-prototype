"""
Gemini agent loop with tool calling.
Handles the conversation flow: user message → Gemini → tool calls → reply.
"""
import json
import logging
from typing import Optional
from google import genai
from google.genai import types

from agent.config import settings
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_DECLARATIONS, execute_tool
from agent import sessions

logger = logging.getLogger(__name__)

_client = None
MODEL = "gemini-3.5-flash-lite"

MAX_TOOL_ROUNDS = 10


def _get_client():
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def handle_message(phone: str, user_text: str) -> str:
    """
    Process an incoming user message through the Gemini agent loop.
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
    if context_msg:
        history.insert(0, {"role": "user", "parts": [{"text": context_msg}]})
        history.insert(1, {"role": "model", "parts": [{"text": "تم استلام السياق. جاهز للخدمة."}]})

    # 4. Call Gemini with tools (loop for tool calls)
    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            response = _get_client().models.generate_content(
                model=MODEL,
                contents=history,
                config=types.GenerateContentConfig(
                    tools=TOOL_DECLARATIONS,
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                ),
            )
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى."

        # Check if response has function calls
        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content:
            return "عذراً، لم أتمكن من فهم طلبك. يرجى إعادة الصياغة."

        has_tool_call = False
        for part in candidate.content.parts:
            if part.function_call:
                has_tool_call = True
                tool_name = part.function_call.name
                tool_args = dict(part.function_call.args) if part.function_call.args else {}

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)
                logger.info(f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:300]}")

                # Add function call and result to history
                history.append({
                    "role": "model",
                    "parts": [part],
                })
                history.append({
                    "role": "user",
                    "parts": [{
                        "function_response": {
                            "name": tool_name,
                            "response": tool_result,
                        }
                    }],
                })

                # Update session context based on tool calls
                _update_session_from_tool(phone, tool_name, tool_args, tool_result)

        if not has_tool_call:
            # Extract text reply
            reply_text = ""
            for part in candidate.content.parts:
                if part.text:
                    reply_text += part.text

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
