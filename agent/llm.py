"""
LLM agent loop with tool calling (OpenAI-compatible API).
Handles the conversation flow: user message → LLM → tool calls → reply.

Targets a self-hosted vLLM (Qwen3.6-27B-FP8) by default; any OpenAI-compatible
endpoint works via LLM_BASE_URL / LLM_MODEL.
"""
import json
import logging
import re
import threading
import time
from typing import Optional
from openai import OpenAI

from agent import callctx
from agent import phone as pnum
from agent.config import settings
from agent.prompts import SYSTEM_PROMPT, system_prompt_for
from agent.tools import TOOLS_OPENAI, execute_tool, tools_for
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


def _sampling(stream=False, channel: str = "whatsapp"):
    """Request parameters shared by the streaming and blocking paths.

    The tool list is per-channel: a phone call also gets call control
    (transfer_to_human / end_call), which means nothing on WhatsApp.
    """
    kwargs = {
        "tools": tools_for(channel),
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


def _execute_tool_with_retry(tool_name: str, tool_args: dict,
                             phone: str = "", channel: str = "whatsapp",
                             call_id: Optional[str] = None) -> dict:
    """Execute tool with retry for transient errors (network, timeout).

    The call binding is established HERE, around the synchronous execution,
    rather than once around the whole turn. A generator that sets a
    ContextVar and then yields does not keep it: Starlette drains a sync
    generator through the threadpool, and each resumption gets a fresh copy
    of the context, so the binding was gone by the time a tool ran and
    `transfer_to_human` saw no call to transfer.
    """
    token = callctx.bind(phone, channel, call_id)
    try:
        return _execute_tool_inner(tool_name, tool_args)
    finally:
        callctx.reset(token)


def _execute_tool_inner(tool_name: str, tool_args: dict) -> dict:
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


# Tool results go into the history and are re-sent on every later turn, so
# a fat one is not paid once — it is paid for the rest of the conversation.
# Measured on this stack: ~5k tokens of prompt costs ~9s to first token, and
# a two-round turn then runs past what a caller will hold the phone for.
# `update_section` alone added ~950 tokens by echoing the whole completeness
# object (every missing field of every section) after a one-field update.
MAX_TOOL_RESULT_CHARS = 1500


def _shrink_tool_result(text: str) -> str:
    """Cap a tool result, keeping it valid-looking to the model.

    Truncating JSON mid-structure invites the model to hallucinate the rest,
    so the cut is marked explicitly and the model is told what happened.
    """
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return text
    return (text[:MAX_TOOL_RESULT_CHARS]
            + f'… [truncated: {len(text) - MAX_TOOL_RESULT_CHARS} more '
              'characters. The call succeeded; ask for a specific field if '
              'you need one that is not shown.]')


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


def _call_llm(messages: list, model: str = None, channel: str = "whatsapp"):
    """Call the LLM, falling back to the secondary model if one is configured."""
    model = model or settings.llm_model
    try:
        _rate_limit()
        return _get_client().chat.completions.create(
            model=model, messages=messages, **_sampling(channel=channel))
    except Exception as e:
        logger.warning(f"Model {model} failed: {e}")
        if settings.llm_fallback_model and model != settings.llm_fallback_model:
            logger.info(f"Trying fallback model: {settings.llm_fallback_model}")
            _rate_limit()
            return _get_client().chat.completions.create(
                model=settings.llm_fallback_model, messages=messages,
                **_sampling(channel=channel))
        raise


def _call_llm_stream(messages: list, model: str = None,
                     channel: str = "whatsapp"):
    """Call the LLM with streaming enabled."""
    model = model or settings.llm_model
    try:
        _rate_limit()
        return _get_client().chat.completions.create(
            model=model, messages=messages,
            **_sampling(stream=True, channel=channel))
    except Exception as e:
        logger.warning(f"Model {model} failed: {e}")
        if settings.llm_fallback_model and model != settings.llm_fallback_model:
            logger.info(f"Trying fallback model: {settings.llm_fallback_model}")
            _rate_limit()
            return _get_client().chat.completions.create(
                model=settings.llm_fallback_model, messages=messages,
                **_sampling(stream=True, channel=channel))
        raise


def _merge_orphaned_user_turns(messages: list) -> list:
    """Collapse consecutive user messages into one.

    A run of user turns with no assistant between them means earlier turns
    were abandoned before they could answer (see _handle_message_stream).
    The turn is flushed properly now, but sessions damaged before that fix
    are still on disk, and a caller who hangs up mid-answer can still
    produce a short run.

    Left alone it compounds: the model sees a conversation where it ignored
    the user three times, and behaves accordingly — the replies get stranger
    until it stops answering usefully. Merging them presents what the user
    actually meant, which is one message asked three ways.
    """
    out = []
    for msg in messages:
        if (msg.get("role") == "user" and out and out[-1].get("role") == "user"
                and isinstance(msg.get("content"), str)
                and isinstance(out[-1].get("content"), str)):
            out[-1] = {**out[-1],
                       "content": f"{out[-1]['content']}\n{msg['content']}"}
            continue
        out.append(msg)
    return out


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
    return _merge_orphaned_user_turns(messages)


def handle_message(phone: str, user_text: str, channel: str = "whatsapp",
                   call_id: Optional[str] = None,
                   system_note: Optional[str] = None) -> str:
    """
    Process an incoming user message through the LLM agent loop.
    Returns the agent's Arabic text reply.

    `channel` selects the system prompt and the tool list; `call_id` binds
    the turn to a live SIP call so the voice tools can act on it.
    """
    return _handle_message(phone, user_text, channel, system_note, call_id)


def _handle_message(phone: str, user_text: str, channel: str,
                    system_note: Optional[str] = None,
                    call_id: Optional[str] = None) -> str:
    analytics.track_message(phone, is_user=True)

    # 1. Load history and append the new user turn
    history = sessions.get_history(phone)
    user_msg = {"role": "user", "content": user_text}
    history.append(user_msg)
    sessions.append_message(phone, user_msg)

    # 2. Context goes on the system message rather than burning a turn
    context_msg = _build_context_message(phone, sessions.get_context(phone),
                                         channel)
    base_prompt = system_prompt_for(channel)
    system_msg = base_prompt
    if context_msg:
        system_msg = base_prompt + "\n\n---\n\n## Current Context\n" + context_msg
    system_msg += _language_note(history)
    if system_note:
        system_msg += "\n\n---\n\n## What just happened\n" + system_note
    messages = _build_messages(history, system_msg)

    # Everything produced this turn is written back to the session at the end,
    # so the next turn can see which tools actually ran and what they returned.
    turn: list[dict] = []

    for round_num in range(MAX_TOOL_ROUNDS):
        token_count = _count_message_tokens(messages)
        if token_count > 3000:
            logger.warning(f"High token count: {token_count} (round {round_num})")

        try:
            response = _call_llm(messages, channel=channel)
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
                tool_result = _execute_tool_with_retry(
                    tool_name, tool_args, phone, channel, call_id)
                analytics.track_tool_call(phone, tool_name, success="error" not in tool_result)
                logger.info(f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:300]}")

                tool_msg = {"role": "tool", "tool_call_id": tc.id,
                            "content": _shrink_tool_result(
                                json.dumps(tool_result, ensure_ascii=False))}
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


def handle_message_stream(phone: str, user_text: str,
                          channel: str = "whatsapp",
                          call_id: Optional[str] = None,
                          system_note: Optional[str] = None):
    """
    Process an incoming user message, yielding progress as it happens.

    Events:
      ("text",  chunk)      append this fragment to the visible reply
      ("tool",  name)       a tool started running
      ("reset", None)       discard what has been shown; it was preamble the
                            model wrote before deciding to call a tool
      ("done",  reply)      the final, authoritative reply text

    `channel` selects the system prompt and the tool list; `call_id` binds
    the turn to a live SIP call so the voice tools can act on it. The
    binding is set here rather than by the caller so it covers the whole
    generator, including the tool calls, which run lazily as it is drained.
    """
    yield from _handle_message_stream(phone, user_text, channel,
                                      system_note, call_id)


def _handle_message_stream(phone: str, user_text: str, channel: str,
                           system_note: Optional[str] = None,
                           call_id: Optional[str] = None):
    """Stream a turn, and ALWAYS write back what happened.

    The user's message is persisted the moment it arrives, but the
    assistant's reply only at the end. A turn that is abandoned in between
    — the caller hung up, the voice engine's HTTP read timed out, the
    browser closed the stream — leaves the user turn in the history with
    no answer after it. Do that a few times and the history is a run of
    consecutive user messages, every later prompt is worse than the last,
    and the conversation degrades until it stops working. Restarting does
    not help, because the damage is in sessions.db.

    So the accumulated turn is flushed from a `finally`, which also runs on
    the GeneratorExit thrown into an abandoned generator.
    """
    analytics.track_message(phone, is_user=True)
    history = sessions.get_history(phone)
    user_msg = {"role": "user", "content": user_text}
    history.append(user_msg)
    sessions.append_message(phone, user_msg)

    context_msg = _build_context_message(phone, sessions.get_context(phone),
                                         channel)
    base_prompt = system_prompt_for(channel)
    system_msg = base_prompt
    if context_msg:
        system_msg = base_prompt + "\n\n---\n\n## Current Context\n" + context_msg
    system_msg += _language_note(history)
    if system_note:
        system_msg += "\n\n---\n\n## What just happened\n" + system_note
    messages = _build_messages(history, system_msg)

    turn: list[dict] = []
    written = False

    try:
      for round_num in range(MAX_TOOL_ROUNDS):
        token_count = _count_message_tokens(messages)
        if token_count > 3000:
            logger.warning(f"High token count: {token_count} (round {round_num})")

        try:
            stream = _call_llm_stream(messages, channel=channel)
        except Exception as e:
            logger.error(f"LLM API error (all models failed): {e}")
            sessions.append_messages(phone, turn)
            written = True
            yield ("reset", None)
            yield ("done", _map_error_to_friendly(str(e)))
            return

        # Process streaming response
        full_content = ""
        tool_calls_data = {}
        started = time.time()
        first_token = None

        try:
          for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # Accumulate content
            if delta.content:
                if first_token is None:
                    first_token = time.time() - started
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
        finally:
            # Releasing the HTTP connection is what frees the model.
            #
            # When a turn is abandoned — the caller hung up, the voice
            # engine's read timed out — GeneratorExit is raised at a yield
            # inside this loop and the stream object is simply dropped. The
            # connection to vLLM stays open and the model keeps generating
            # into it. Do that a few times in one conversation and the
            # server is busy serving callers who left: later requests then
            # queue behind them and never even get response headers, which
            # is exactly what "it just stopped responding" looked like.
            try:
                stream.close()
            except Exception:
                pass
            logger.info(
                f"LLM round {round_num}: {token_count} tok prompt, "
                f"first token {first_token if first_token is None else round(first_token, 2)}s, "
                f"total {time.time() - started:.1f}s")

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

            # Anything streamed this round was the model thinking out loud
            # before deciding to call a tool — it is not part of the answer.
            if full_content.strip():
                yield ("reset", None)

            # Execute each tool call
            for tc in tool_calls_data.values():
                tool_name = tc["name"]
                yield ("tool", tool_name)

                try:
                    tool_args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")
                tool_result = _execute_tool_with_retry(
                    tool_name, tool_args, phone, channel, call_id)
                analytics.track_tool_call(phone, tool_name, success="error" not in tool_result)
                logger.info(f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:300]}")
                # Whether it worked, so a channel acting on a tool (the
                # phone hanging up or transferring) does not act on one
                # that failed.
                yield ("tool_result", {"name": tool_name,
                                       "ok": "error" not in tool_result})

                tool_msg = {"role": "tool", "tool_call_id": tc["id"],
                            "content": _shrink_tool_result(
                                json.dumps(tool_result, ensure_ascii=False))}
                messages.append(tool_msg)
                turn.append(tool_msg)

                _update_session_from_tool(phone, tool_name, tool_args, tool_result)
        else:
            reply = (full_content or "").strip()
            if not reply:
                reply = "عذراً، لم أتمكن من إيجاد إجابة مناسبة."
                yield ("reset", None)
            turn.append({"role": "assistant", "content": reply})
            sessions.append_messages(phone, turn)
            written = True
            analytics.track_message(phone, is_user=False)
            yield ("done", reply)
            return

      # Exhausted tool rounds
      sessions.append_messages(phone, turn)
      written = True
      analytics.track_message(phone, is_user=False)
      yield ("reset", None)
      yield ("done", "عذراً، أحتاج خطوات إضافية. يرجى التواصل مع موظف خدمة المستفيدين.")
    finally:
        if not written and turn:
            # Abandoned mid-turn (GeneratorExit, or an exception on the way
            # out). Persist what did happen so the history does not end on a
            # user message with no answer.
            sessions.append_messages(phone, turn)
            logger.warning(
                f"Turn for {phone} was abandoned after {len(turn)} message(s) "
                "— flushed so the history stays well-formed")


_ARABIC_LETTER = re.compile(r"[؀-ۿ]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def _language_note(history: list) -> str:
    """Which language this conversation is in, decided here rather than left
    to the model to infer.

    A turn that is only digits — "01712345", "1985" — carries no language at
    all, and it is what every dictated phone number, national ID and birth
    year looks like. With no English word in front of it and an Arabic
    `reply_ar` coming back from the tool, the model mirrors the tool and
    switches language mid-exchange. Seen on a live call: an English caller
    reading their number out was answered in Arabic from the second group
    onward, at the exact moment they were least able to follow.

    The rule is "the last user turn that actually had words in it wins", and
    that is a scan, not a judgement — so it is done here and stated as a
    fact rather than asked for in the prompt.
    """
    for msg in reversed(history):
        if msg.get("role") != "user":
            continue
        text = msg.get("content") or ""
        arabic = len(_ARABIC_LETTER.findall(text))
        latin = len(_LATIN_LETTER.findall(text))
        if not arabic and not latin:
            continue                      # digits only: no language in it
        lang = "العربية" if arabic >= latin else "English"
        return ("\n\n---\n\n## Reply language (decided, not negotiable)\n"
                f"The caller is speaking {lang}. Reply only in {lang}, "
                "including when a tool hands you Arabic `reply_ar` — "
                "translate it. The caller's latest turn may be bare digits; "
                "that is a phone number, not a change of language.")
    return ""


def caller_line(phone: str, channel: str) -> str:
    """What the channel already told us about who this is.

    On a call the ANI arrives with the INVITE, before anyone speaks. It is
    the one piece of data on the whole call that speech recognition cannot
    get wrong. The agent asked for it anyway — "Could you please provide
    your phone number?", verbatim, on a live call — and then had to
    reassemble it from a caller reading digits in groups across several
    utterances, each group transcribed on its own. Saying plainly that the
    number is already in hand removes that entire exchange.

    An extension is not a phone number. On the FreeSWITCH rig the ANI is
    `1000`, and telling the model to file a family under `1000` would be
    worse than asking. When the number is unusable the agent is told that
    too, so it knows to collect one.
    """
    if channel != "voice":
        return ""
    if pnum.usable(phone):
        return (
            f"\n\nرقم المتصل (من شبكة الاتصال، وليس من التعرف على الصوت): "
            f"{phone}\n"
            "هذا الرقم مؤكد ولا يحتاج تأكيد. لا تسأل المتصل عن رقم جواله ولا "
            "تطلب منه قراءته. استخدمه مباشرة في check_phone و create_file و "
            "create_ticket باستدعاء الأداة بدون تمرير phone. "
            "اسأل عن رقم آخر فقط اذا قال المتصل صراحة انه يريد تسجيل رقم مختلف.\n"
            # Speech synthesis reads a run of digits as a quantity — "nine
            # hundred and sixty-six billion…" — so the spoken form is given
            # ready-made rather than left to the model to space out.
            f"اذا احتجت نطق الرقم اقرأه هكذا: {pnum.spaced(phone)}")
    return (
        f"\n\nرقم المتصل غير متاح من شبكة الاتصال (وصل: {phone or 'لا شيء'}) — "
        "هذا رقم داخلي وليس رقم جوال. اذا احتجت رقم الجوال اطلبه من المتصل، "
        "واقرأه عليه رقما رقما للتأكيد قبل الحفظ.")


def _build_context_message(phone: str, context: Optional[dict],
                           channel: str = "whatsapp") -> str:
    """Build a context injection message from the WhatsApp inbound result."""
    if not context:
        return caller_line(phone, channel)

    if not context.get("known"):
        return (
            f"سياق المحادثة: متصل جديد (غير مسجل في النظام). رقم الجوال: {phone}. "
            "ابدأ بالترحيب واسأل عن أهدافه. "
            f"عند إنشاء تذكرة استخدم phone={phone}."
            + caller_line(phone, channel)
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

    return "\n".join(ctx_parts) + caller_line(phone, channel)


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
