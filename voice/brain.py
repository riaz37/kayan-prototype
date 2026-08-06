"""The agent, seen from the phone.

The deliberate design decision of this whole integration lives here: the
voice engine does **not** think. It has no LLM client, no system prompt, no
tool list and no conversation history of its own. It transcribes what the
caller said, hands the text to the existing Kayan agent over HTTP, and
speaks whatever comes back.

esap-voice's cascade transport ran its own LLM loop with its own message
history. Porting that verbatim would have given Kayan two brains — a
WhatsApp one and a phone one — that would drift apart within a week, and it
would have re-opened the failure in WORKLOG §9: the phone's history would
be a separate, text-only transcript, so the model could not see which tools
had actually run and would start confirming things it never did.

Instead the phone is another door into the same agent. It reuses the agent's
22 tools, its TOOL DISCIPLINE prompt, and — because agent/sessions.py is
keyed by phone number — the *same conversation*. Someone who started
registering on WhatsApp and then rings in continues where they left off,
with the slots they already filled.

Two HTTP surfaces, both already existing before this work:

  backend :8001  POST /voice/call-start, /voice/call-end/{id}
                 (the call_sessions table and console call log)
  agent   :8002  POST /agent/chat?stream=true  (SSE, one turn)
"""
import json
import logging
from typing import Iterator, Optional, Tuple

import httpx

from . import diag
from .config import settings

logger = logging.getLogger(__name__)

# Spoken when the backend cannot be reached on answer. A caller who hears
# nothing assumes the line is dead; better a generic greeting than silence.
FALLBACK_GREETING_AR = "حياكم الله في جمعية كيان للايتام. كيف اقدر اخدمكم؟"

# Spoken when the agent itself fails mid-call.
AGENT_ERROR_AR = ("عذرا، صار عندنا خلل تقني بسيط. "
                  "ممكن تعيدون كلامكم مرة ثانية؟")


class CallBrain:
    """One call's conversation with the Kayan agent."""

    def __init__(self, phone: str, direction: str = "inbound",
                 sip_call_id: Optional[str] = None,
                 to_number: str = "966112925559"):
        self.phone = phone
        self.direction = direction
        self.sip_call_id = sip_call_id
        self.to_number = to_number
        self.call_id: Optional[str] = None
        self.context: Optional[dict] = None
        self.identified = False
        self.greeting_ar = FALLBACK_GREETING_AR
        # Tool names seen this call, for the call-end outcome.
        self.tools_used: list = []
        self._client = httpx.Client(timeout=30.0)

    # ---------- lifecycle ----------

    def start(self) -> str:
        """Open the call session; returns the greeting to speak.

        A failure here must not drop the caller — they have already been
        answered. We log it, greet generically, and carry on without
        context; the agent then behaves as it does for an unknown number.
        """
        body = {"from_number": self.phone, "to_number": self.to_number,
                "direction": self.direction}
        if self.sip_call_id:
            body["sip_call_id"] = self.sip_call_id
        try:
            r = self._client.post(
                f"{settings.backend_url}/voice/call-start", json=body)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            diag.log(f"brain: call-start failed ({e!r}) — greeting generically")
            return self.greeting_ar
        self.call_id = data.get("call_id")
        self.identified = bool(data.get("identified"))
        self.context = data.get("context") or None
        self.greeting_ar = data.get("greeting_ar") or FALLBACK_GREETING_AR
        diag.log(f"brain: call {self.call_id} started for {self.phone} "
                 f"(identified={self.identified})")
        return self.greeting_ar

    def end(self, outcome: str = "resolved_by_bot",
            intent: Optional[str] = None, duration_sec: int = 0,
            transcript_ar: Optional[str] = None) -> None:
        """Close the call session with its outcome, for reporting."""
        if not self.call_id:
            return
        body = {"outcome": outcome, "duration_sec": int(duration_sec)}
        if intent:
            body["intent"] = intent
        if transcript_ar:
            body["transcript_ar"] = transcript_ar
        try:
            r = self._client.post(
                f"{settings.backend_url}/voice/call-end/{self.call_id}",
                json=body)
            r.raise_for_status()
            diag.log(f"brain: call {self.call_id} logged as {outcome} "
                     f"({duration_sec}s)")
        except Exception as e:
            diag.log(f"brain: call-end failed for {self.call_id}: {e!r}")

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def outcome(self) -> str:
        """What to record for this call, from the tools the agent ran."""
        if "transfer_to_human" in self.tools_used:
            # /voice/transfer already set this; recording it again is
            # harmless and keeps the outcome right if the transfer tool
            # ran but the REFER never completed.
            return "escalated_to_agent"
        if "create_ticket" in self.tools_used:
            return "ticket_created"
        return "resolved_by_bot"

    # ---------- one turn ----------

    def turn(self, text: str,
             system_note: Optional[str] = None
             ) -> Iterator[Tuple[str, Optional[str]]]:
        """Stream one turn of the conversation.

        Yields the agent's own SSE events, unwrapped:

            ("text",  chunk)   speak this fragment
            ("tool",  name)    a tool started running
            ("tool_result", {"name","ok"})  …and whether it worked
            ("reset", None)    discard what was streamed; it was preamble
            ("done",  reply)   the final, authoritative reply text
            ("error", message) speak this and end the turn

        The transport turns "text" into speech as sentences complete, so
        the caller hears the reply begin while the rest is still being
        generated. That is the whole reason for consuming SSE here rather
        than calling ?stream=false and waiting for the full reply.
        """
        body = {
            "from_number": self.phone,
            "text_ar": text,
            "channel": "voice",
        }
        if self.call_id:
            body["call_id"] = self.call_id
        if system_note:
            # Something happened on the line that the agent could not have
            # known — a transfer that failed, a line it already spoke. It
            # rides in the system prompt for this turn only.
            body["system_note"] = system_note
        if self.context is not None:
            # Pass it every turn: the agent stores it on the session, and
            # this keeps a restarted agent from falling back to
            # /whatsapp/inbound and opening a WhatsApp window for a caller.
            body["context"] = self.context
        try:
            with self._client.stream(
                    "POST", f"{settings.agent_url}/agent/chat",
                    json=body, params={"stream": "true"},
                    timeout=settings.agent_timeout_seconds) as response:
                if response.status_code != 200:
                    response.read()
                    diag.log(f"brain: agent returned {response.status_code}")
                    yield ("error", AGENT_ERROR_AR)
                    return
                for event in _sse_events(response):
                    kind = event.get("type")
                    if kind == "delta":
                        yield ("text", event.get("text", ""))
                    elif kind == "tool":
                        name = event.get("name", "")
                        if name:
                            self.tools_used.append(name)
                            diag.log(f"brain: tool {name}")
                        yield ("tool", name)
                    elif kind == "tool_result":
                        yield ("tool_result", {"name": event.get("name", ""),
                                               "ok": bool(event.get("ok"))})
                    elif kind == "reset":
                        yield ("reset", None)
                    elif kind == "done":
                        yield ("done", event.get("reply", ""))
                        return
                    elif kind == "error":
                        diag.log(f"brain: agent error event: "
                                 f"{event.get('detail', '')[:200]}")
                        yield ("error", event.get("message") or AGENT_ERROR_AR)
                        return
        except Exception as e:
            diag.log(f"brain: agent stream failed: {e!r}")
            yield ("error", AGENT_ERROR_AR)


def _sse_events(response) -> Iterator[dict]:
    """Parse `data:` lines off an SSE response into dicts."""
    for line in response.iter_lines():
        if not line:
            continue
        # httpx yields str for iter_lines(); be tolerant of bytes.
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            yield json.loads(payload)
        except ValueError:
            diag.log(f"brain: unparseable SSE line {payload[:120]!r}")
