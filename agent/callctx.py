"""Which call (if any) the turn being processed belongs to.

The voice tools — `transfer_to_human`, `end_call` — act on a live SIP call,
so they need its `call_id`. That id must NOT be a tool parameter: the model
would have to carry it through the conversation and would sooner or later
invent one, which is exactly the class of bug WORKLOG §9 is about. It is
also not something a beneficiary said, so it does not belong in the prompt.

Instead the agent sets it here for the duration of the turn and the tool
handlers read it. A ContextVar rather than a global because FastAPI runs
turns on a threadpool and two calls can be in flight at once.
"""
import contextvars
from typing import Optional

_call = contextvars.ContextVar("kayan_call", default=None)


def bind(phone: str, channel: str = "whatsapp",
         call_id: Optional[str] = None):
    """Bind the current turn to a channel/call. Returns the token to reset."""
    return _call.set({"phone": phone, "channel": channel,
                      "call_id": call_id})


def reset(token) -> None:
    try:
        _call.reset(token)
    except (ValueError, LookupError):
        # The turn finished on a different context than it started on;
        # the binding dies with that context anyway.
        pass


def current() -> dict:
    return _call.get() or {}


def call_id() -> Optional[str]:
    return current().get("call_id")


def phone() -> str:
    """The number this turn came from — the caller's ANI on a call.

    A tool that needs "the beneficiary's phone number" should prefer this
    over anything transcribed. The line already carried it; asking a caller
    to read out the number they are calling from is both needless and the
    single worst thing to put through speech recognition.
    """
    return current().get("phone") or ""


def channel() -> str:
    return current().get("channel") or "whatsapp"


def is_voice() -> bool:
    return channel() == "voice"
