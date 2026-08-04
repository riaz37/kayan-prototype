"""
Kayan WhatsApp Agent — FastAPI Application
Webhook endpoint for Meta WhatsApp Cloud API + health check.
Follows official Meta Cloud API documentation.
"""
import json
import logging
import os
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agent.config import settings
from agent.whatsapp import (
    verify_webhook, validate_signature, extract_message,
    send_text, send_template, send_read_receipt, normalize_phone_for_lookup,
)
from agent.sessions import get_session, set_context, get_context, clear_session, clear_all_sessions
from agent import llm as agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kayan WhatsApp Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# Deduplication: track processed message_ids to avoid retry duplicates
_processed_messages: dict[str, float] = {}  # message_id -> timestamp
DEDUP_TTL = 300  # 5 minutes


def _is_duplicate(message_id: str) -> bool:
    """Check if message was already processed. Cleans old entries."""
    now = time.time()
    # Clean old entries
    expired = [k for k, v in _processed_messages.items() if now - v > DEDUP_TTL]
    for k in expired:
        del _processed_messages[k]
    # Check duplicate
    if message_id and message_id in _processed_messages:
        return True
    if message_id:
        _processed_messages[message_id] = now
    return False


class ChatRequest(BaseModel):
    from_number: str
    text_ar: str


class ChatResponse(BaseModel):
    reply: str
    context: Optional[dict] = None
    known_beneficiary: bool = False


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "kayan-whatsapp-agent"}


@app.get("/webhook")
async def webhook_verify(request: Request):
    """
    Meta webhook verification handshake.
    Official doc: GET with hub.mode=subscribe, hub.verify_token, hub.challenge.
    Return 200 with hub.challenge if valid, 403 otherwise.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    result = verify_webhook(mode, token, challenge)
    if result:
        logger.info("Webhook verified successfully")
        return Response(content=str(result), media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def webhook_receive(request: Request):
    """
    Receive inbound WhatsApp messages from Meta Cloud API.
    Official doc: POST with X-Hub-Signature-256 header for validation.
    Must respond within ~5 seconds; do heavy work asynchronously.
    """
    # 1. Read raw body for signature validation (must be before JSON parsing)
    raw_body = await request.body()

    # 2. Validate X-Hub-Signature-256 (official doc requirement)
    # Skip validation in test mode (no app secret configured)
    signature = request.headers.get("X-Hub-Signature-256", "")
    if settings.whatsapp_app_secret and signature and not validate_signature(raw_body, signature):
        logger.warning("Invalid webhook signature — rejecting")
        return Response(status_code=403)

    # 3. Parse JSON payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON payload")
        return Response(status_code=400)

    logger.info(f"Webhook payload: {json.dumps(payload, ensure_ascii=False)[:500]}")

    # 4. Extract message
    msg = extract_message(payload)
    if not msg:
        # Not a message (status update, echo, etc.)
        return {"status": "ignored"}

    sender = msg.get("from", "")
    text = msg.get("text", "")
    msg_type = msg.get("type", "")
    message_id = msg.get("message_id", "")

    if not sender:
        return {"status": "ignored"}

    # 5. Deduplication — skip if already processed (Meta retries webhooks)
    if _is_duplicate(message_id):
        logger.info(f"Duplicate message {message_id} from {sender} — skipping")
        return {"status": "ok", "action": "duplicate"}

    logger.info(f"Inbound from {sender}: [{msg_type}] {text[:100]}")

    # 6. Send read receipt (optional but recommended)
    # send_read_receipt used to be called without being imported, so this block
    # raised NameError on every message and the bare except hid it.
    if message_id and settings.whatsapp_access_token:
        try:
            send_read_receipt(message_id)
        except Exception as e:
            logger.debug(f"Read receipt failed (non-critical): {e}")

    # 7. Handle non-text messages
    if msg_type != "text" or not text:
        reply = "عذراً، أستطيع حالياً التعامل مع الرسائل النصية فقط. يرجى إرسال رسالتك كتابةً."
        _send_reply(sender, reply)
        return {"status": "ok", "action": "unsupported_type"}

    # 8. Load or create session
    sess = get_session(sender)

    # 9. If first message or context expired, load context from backend
    if not sess.get("context"):
        _load_context(sender, text)

    # 10. Process through agent
    try:
        reply = agent.handle_message(sender, text)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        # Detect user language from their message
        import re as _re
        has_arabic = bool(_re.search(r'[\u0600-\u06FF]', text))
        if has_arabic:
            reply = "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى أو التواصل مع خدمة المستفيدين."
        else:
            reply = "Sorry, a technical error occurred. Please try again or contact beneficiary services."

    logger.info(f"Reply to {sender}: {reply[:100]}")

    # 11. Send reply — detect Baileys bridge vs Meta API
    is_baileys = payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("metadata", {}).get("phone_number_id") == "baileys"
    if is_baileys:
        _send_reply_baileys(sender, reply)
    else:
        _send_reply(sender, reply)

    return {"status": "ok"}


def _load_context(phone: str, text: str):
    """Load beneficiary context from backend."""
    try:
        import httpx
        resp = httpx.post(
            f"{settings.backend_url}/whatsapp/inbound",
            json={"from_number": phone, "text_ar": text},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            set_context(phone, data.get("context", {}))
            logger.info(f"Loaded context for {phone}: known={data.get('known_beneficiary')}")
    except Exception as e:
        logger.warning(f"Failed to load context: {e}")


def _send_reply_baileys(to: str, text: str):
    """Send reply via Baileys bridge HTTP server."""
    import httpx
    # 8002 is the agent's own port — the old default made this POST to itself.
    bridge_port = int(os.environ.get("BRIDGE_PORT", "8003"))
    try:
        resp = httpx.post(
            f"http://localhost:{bridge_port}/send",
            json={"phone": to, "text": text},
            timeout=10,
        )
        logger.info(f"Baileys reply to {to}: {resp.json()}")
    except Exception as e:
        logger.error(f"Failed to send via Baileys: {e}")


def _send_reply(to: str, text: str):
    """Send reply via WhatsApp, choosing free-form or template based on window."""
    try:
        # Check session window
        import httpx
        lookup_phone = normalize_phone_for_lookup(to)
        resp = httpx.get(
            f"{settings.backend_url}/whatsapp/session/{lookup_phone}",
            timeout=10,
        )
        if resp.status_code == 200:
            session_data = resp.json()
            window = session_data.get("window", {})
            if window.get("open"):
                # Free-form send
                result = send_text(to, text)
                logger.info(f"Sent free-form to {to}: {result}")
                return
            else:
                # Window closed — try template
                logger.info(f"Window closed for {to}, sending template")
                result = send_template(to, "TPL-REG-OK", params=[{"type": "text", "text": to}])
                logger.info(f"Sent template to {to}: {result}")
                return
    except Exception as e:
        logger.warning(f"Failed to check session window: {e}")

    # Fallback: try free-form
    try:
        send_text(to, text)
    except Exception as e:
        logger.error(f"Failed to send reply to {to}: {e}")


def _error_reply(text: str) -> str:
    """Apologise in whichever language the user wrote in."""
    import re as _re
    if _re.search(r"[\u0600-\u06FF]", text):
        return "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى."
    return "Sorry, a technical error occurred. Please try again."


@app.post("/agent/chat", tags=["agent"])
async def agent_chat(req: ChatRequest, stream: bool = True):
    """
    Test the agent from the browser. Bypasses the Meta webhook.

    Streams Server-Sent Events by default. A turn that calls three tools is
    three LLM round trips (~2s before the first word, measured), and the
    endpoint used to sit silent for all of it. Pass ?stream=false for the
    original single JSON response — scripts use that, and so does the WhatsApp
    path, which cannot stream a message anyway.

    SSE events, one JSON object per `data:` line:
        {"type":"delta","text":"…"}   append to the visible reply
        {"type":"tool","name":"…"}    a tool started running
        {"type":"reset"}              discard what is shown; it was preamble
        {"type":"done","reply":"…","context":{…},"known_beneficiary":bool}
        {"type":"error","message":"…"}
    """
    phone = req.from_number
    text = req.text_ar
    logger.info(f"Agent chat from {phone}: {text[:100]}")

    # Load context if first message
    if not get_session(phone).get("context"):
        _load_context(phone, text)

    if not stream:
        try:
            reply = agent.handle_message(phone, text)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            reply = _error_reply(text)
        context = get_context(phone)
        return ChatResponse(reply=reply, context=context,
                            known_beneficiary=bool(context and context.get("known")))

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def event_stream():
        final = ""
        try:
            for kind, value in agent.handle_message_stream(phone, text):
                if kind == "text":
                    yield sse({"type": "delta", "text": value})
                elif kind == "tool":
                    yield sse({"type": "tool", "name": value})
                elif kind == "reset":
                    yield sse({"type": "reset"})
                elif kind == "done":
                    final = value
        except Exception as e:
            logger.exception("Agent stream error")
            yield sse({"type": "error", "message": _error_reply(text), "detail": str(e)})
            return

        context = get_context(phone)
        yield sse({"type": "done", "reply": final, "context": context,
                   "known_beneficiary": bool(context and context.get("known"))})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx and some proxies buffer responses by default, which defeats SSE
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/agent/send-text", tags=["agent"])
async def agent_send_text(payload: dict):
    """Send a WhatsApp text message from backend CRM."""
    to = payload.get("to", "")
    text = payload.get("text", "")
    if not to or not text:
        return {"error": "missing 'to' or 'text'"}
    try:
        result = send_text(to, text)
        logger.info(f"CRM send_text to {to}: {result}")
        return {"ok": True, "result": result}
    except Exception as e:
        logger.error(f"CRM send_text failed: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/agent/session/{phone}/history", tags=["agent"])
async def agent_session_history(phone: str):
    """Get WhatsApp conversation history for a phone."""
    from agent.sessions import get_session
    sess = get_session(phone)
    return {"phone": phone, "history": sess.get("history", [])}


@app.post("/agent/session/{phone}/reset", tags=["agent"])
async def agent_session_reset(phone: str):
    """Reset a session — clears history and context."""
    clear_session(phone)
    logger.info(f"Session reset for {phone}")
    return {"status": "ok", "phone": phone}


@app.post("/agent/sessions/clear-all", tags=["agent"])
async def agent_sessions_clear_all():
    """Clear all sessions."""
    clear_all_sessions()
    logger.info("All sessions cleared")
    return {"status": "ok", "message": "All sessions cleared"}


@app.get("/", tags=["system"])
def root():
    return {
        "service": "Kayan WhatsApp Agent",
        "version": "1.1.0",
        # Report what is actually configured instead of a hardcoded name that
        # drifted from the model in use (it said "DeepSeek V4 Flash" while
        # calling Qwen through OpenRouter).
        "model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "thinking_enabled": settings.llm_enable_thinking,
        "backend": settings.backend_url,
        "webhook": "/webhook",
        "health": "/health",
    }
