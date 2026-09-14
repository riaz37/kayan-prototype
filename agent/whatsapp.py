"""
Meta WhatsApp Cloud API helpers.
Handles webhook verification, signature validation, sending text messages,
and sending templates. Follows official Meta Cloud API documentation.
"""
import hashlib
import hmac
import logging
import threading
from typing import Optional
import httpx
from agent.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_API_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def normalize_phone_for_api(phone: str) -> str:
    """
    Normalize phone number for WhatsApp Cloud API.
    Official API expects digits-only with country code (no + prefix needed).
    The 'from' field from webhook is already in correct format (e.g. 8801813316904).
    """
    digits = "".join(c for c in phone if c.isdigit())
    return digits


def normalize_phone_for_lookup(phone: str) -> str:
    """
    Normalize phone for beneficiary lookup (without + prefix).
    Matches the backend store.norm_phone format.
    """
    digits = "".join(c for c in phone if c.isdigit())
    return digits


def verify_webhook(mode: str, token: str, challenge: Optional[str] = None) -> Optional[str]:
    """
    Verify the Meta webhook subscription handshake.
    Official doc: check hub.mode=subscribe and hub.verify_token matches,
    then respond with hub.challenge value.
    """
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return challenge
    return None


def validate_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Validate X-Hub-Signature-256 header.
    Official doc: HMAC-SHA256 over raw request body, keyed by App Secret.
    Must use raw bytes, not re-serialized JSON.
    """
    if not settings.whatsapp_app_secret or not signature_header:
        return False

    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def send_text(to: str, text: str) -> dict:
    """
    Send a free-form text message via WhatsApp Cloud API.
    Official doc: POST /{VERSION}/{PHONE_NUMBER_ID}/messages
    """
    url = f"{GRAPH_API_URL}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalize_phone_for_api(to),
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text,
        },
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    return resp.json()


def _log_delivery_async(to: str, text: str, delivered: bool, provider_response: dict, kind: str) -> None:
    """Fire-and-forget: persist the send outcome against the matched beneficiary
    so a failed delivery isn't silently lost. Runs off-thread so it never
    delays the reply to the user."""
    def _run():
        try:
            httpx.post(
                f"{settings.backend_url}/whatsapp/log-delivery",
                json={
                    "to": to,
                    "body_ar": text,
                    "delivered": delivered,
                    "provider_response": str(provider_response)[:4000],
                    "kind": kind,
                },
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Failed to log WhatsApp delivery for {to}: {e}")

    threading.Thread(target=_run, daemon=True).start()


def send_text_2whats(to: str, text: str) -> dict:
    """
    Send a free-form WhatsApp text via the 2whats.com provider (non-Meta).
    GET /api/send per the vendor's documented endpoint.
    """
    params = {
        "mobile": settings.twowhats_mobile,
        "password": settings.twowhats_password,
        "instanceid": settings.twowhats_instanceid,
        "message": text,
        "numbers": normalize_phone_for_api(to),
        "json": 1,
        "type": 1,
    }
    try:
        resp = httpx.get("https://www.2whats.com/api/send", params=params, timeout=15)
        try:
            payload = resp.json()
        except ValueError:
            payload = {"raw": resp.text}
        return {"ok": resp.status_code == 200, "status_code": resp.status_code, "response": payload}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_text_and_log(to: str, text: str, kind: str = "agent_reply") -> dict:
    """Send a free-form text message via the 2whats.com provider and log the
    real delivery outcome (success/failure + provider response) against the
    matched beneficiary. Use this instead of send_text() for any message the
    agent sends on its own, so failed sends show up in the CRM notification log."""
    result = send_text_2whats(to, text)
    delivered = bool(result.get("ok"))
    if not delivered:
        logger.error(f"WhatsApp send failed for {to}: {result}")
    _log_delivery_async(to, text, delivered, result, kind)
    return result


def send_template(to: str, template_name: str, lang: str = "ar",
                  params: Optional[list] = None) -> dict:
    """
    Send an approved template message via WhatsApp Cloud API.
    Official doc: POST /{VERSION}/{PHONE_NUMBER_ID}/messages with type=template
    """
    url = f"{GRAPH_API_URL}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    template_body: dict = {
        "name": template_name,
        "language": {"code": lang},
    }
    if params:
        template_body["components"] = [
            {"type": "body", "parameters": params}
        ]
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalize_phone_for_api(to),
        "type": "template",
        "template": template_body,
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    return resp.json()


def send_read_receipt(message_id: str) -> dict:
    """Mark a message as read (typing indicator + read receipt)."""
    url = f"{GRAPH_API_URL}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    return resp.json()


def extract_message(payload: dict) -> Optional[dict]:
    """
    Extract the first inbound message from a Meta webhook payload.
    Official doc: entry[].changes[].value.messages[] for messages,
                  entry[].changes[].value.contacts[] for sender info.
    Returns dict with keys: from, message_id, type, text, timestamp, contact_name.
    Returns None if no message found (e.g. status update).
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages", [])
        if not messages:
            return None
        msg = messages[0]
        contact = value.get("contacts", [{}])[0]
        result = {
            "from": msg.get("from", ""),
            "message_id": msg.get("id", ""),
            "type": msg.get("type", ""),
            "timestamp": msg.get("timestamp", ""),
            "contact_name": contact.get("profile", {}).get("name", ""),
        }
        if msg.get("type") == "text":
            result["text"] = msg["text"].get("body", "")
        elif msg.get("type") == "image":
            result["image"] = msg["image"].get("id", "")
            result["mime_type"] = msg["image"].get("mime_type", "")
        elif msg.get("type") == "document":
            result["document"] = msg["document"].get("id", "")
            result["document_name"] = msg["document"].get("filename", "")
            result["mime_type"] = msg["document"].get("mime_type", "")
        elif msg.get("type") == "audio":
            result["audio"] = msg["audio"].get("id", "")
        elif msg.get("type") == "interactive":
            result["interactive"] = msg.get("interactive", {})
        elif msg.get("type") == "button":
            result["button"] = msg.get("button", {})
        return result
    except (KeyError, IndexError):
        return None
