"""Regression tests for the voice channel.

The rule from esap-voice worth keeping: anything a live call got wrong gets
a test before it gets a fix. Every test here corresponds to something that
actually misbehaved on a real SIP call through FreeSWITCH during this work,
or to a rule that must not be quietly undone.

No telephony is involved — pyVoIP, RTP and the PBX are exercised by
scripts/voice_call_test.py, which places a real call.
"""
import audioop
import queue
import threading

from voice.transport.kayan import (
    KayanVoiceTransport, already_said, split_sentences,
)


# ---------------------------------------------------------------- sentences
def test_arabic_question_mark_ends_a_sentence():
    """`؟` is its own code point. If it is not a sentence ender the caller
    hears nothing until the whole paragraph has been generated."""
    ready, rest = split_sentences("كيف اقدر اخدمكم اليوم؟ وش الي تحتاجونه؟", 4)
    assert ready, "an Arabic question mark must close a chunk"
    assert ready[0].endswith("؟")


def test_a_decimal_point_is_not_a_sentence_end():
    ready, rest = split_sentences("المبلغ 1500.50 ريال", 4)
    assert ready == []
    assert "1500.50" in rest


def test_long_run_on_text_is_split_anyway():
    """A model that never punctuates must not block playback forever."""
    ready, _ = split_sentences("كلمة " * 200, 4)
    assert ready, "run-on text has to be cut somewhere"


def test_already_said_catches_a_repeated_closing_line():
    """Models repeat their goodbye after a tool round; the caller must not
    hear the same sentence twice."""
    assert already_said("شكرا لتواصلكم. مع السلامة.", "مع السلامة.")
    assert not already_said("شكرا لتواصلكم.", "كيف اقدر اخدمكم؟")


# ------------------------------------------------------------------ the VAD
def _transport():
    """A transport carrying only the state the VAD touches.

    Constructing the real thing needs an answered pyVoIP call, which is the
    part these tests are deliberately not exercising.
    """
    t = object.__new__(KayanVoiceTransport)
    t._vad_lock = threading.Lock()
    t._last_frame_at = 0.0
    t._capturing = False
    t._voiced = 0
    t._silent = 0
    t._preroll = []
    t._utter = bytearray()
    t._voiced_frames = 0
    t._gen = 0
    t._end_after_turn = False
    t.wants_hangup = False
    t._end_silence_frames = 25
    t._utter_q = queue.Queue()
    t._playout = []
    t._last_bot_frame = 0.0
    t._n_interrupts = 0
    t._hangup_hold_until = 0.0
    return t


def _tone(rms_target: int, frames: int = 1) -> bytes:
    """A frame of alternating samples — loud, and not constant DC."""
    sample = int(rms_target).to_bytes(2, "little", signed=True)
    other = int(-rms_target).to_bytes(2, "little", signed=True)
    return (sample + other) * (80 * frames)


def test_a_constant_dc_frame_is_never_speech():
    """When RTP resumes after a gap pyVoIP hands over frames of one repeated
    sample. That is full-scale DC — louder than any voice — and the VAD read
    it as the caller shouting, opening an utterance and firing a barge-in
    that cut the agent off mid-reply."""
    t = _transport()
    rail = b"\x00\x80" * 160          # every sample identical
    assert audioop.rms(rail, 2) > 30000, "the rail really is full scale"
    assert KayanVoiceTransport._is_dc_rail(rail)
    for _ in range(10):
        t._handle_caller_frame(rail)
    assert not t._capturing, "a DC rail must not open an utterance"
    assert t._utter_q.empty()


def test_real_speech_still_opens_an_utterance():
    """The DC guard must not deafen the VAD to actual speech."""
    t = _transport()
    for _ in range(5):
        t._handle_caller_frame(_tone(3000))
    assert t._capturing


def test_an_utterance_closes_when_the_caller_stops_transmitting():
    """FreeSWITCH sends no RTP during silence, and real telephony does the
    same under silence suppression. The quiet-frame counter never advances,
    so without a wall-clock check the utterance stays open forever and the
    agent never answers."""
    t = _transport()
    for _ in range(15):              # enough voiced frames to be a real turn
        t._handle_caller_frame(_tone(3000))
    assert t._capturing
    assert t._utter_q.empty(), "still talking"

    t._last_frame_at -= 5.0          # …and then the audio simply stops
    t._idle_check()

    assert not t._capturing
    assert not t._utter_q.empty(), "the turn must be closed and queued"


def test_a_brief_blip_is_dropped_not_transcribed():
    t = _transport()
    for _ in range(2):
        t._handle_caller_frame(_tone(3000))
    t._last_frame_at -= 5.0
    t._idle_check()
    assert t._utter_q.empty(), "200ms of noise is not a turn"


# ------------------------------------------------------- channel separation
def test_call_control_tools_are_not_offered_on_whatsapp():
    from agent.tools import VOICE_ACTION_TOOLS, tools_for

    text_tools = {t["function"]["name"] for t in tools_for("whatsapp")}
    for name in VOICE_ACTION_TOOLS:
        assert name not in text_tools


def test_voice_prompt_overrides_come_last_and_forbid_markdown():
    """The voice rules are appended after the base prompt so they win, and
    they must actually carry the rules the phone depends on."""
    from agent.prompts import SYSTEM_PROMPT, VOICE_SYSTEM_PROMPT

    assert VOICE_SYSTEM_PROMPT.startswith(SYSTEM_PROMPT)
    tail = VOICE_SYSTEM_PROMPT[len(SYSTEM_PROMPT):]
    assert "PHONE CALL" in tail
    assert "markdown" in tail.lower()
    # TOOL DISCIPLINE is inherited, not restated — losing it is the bug
    # WORKLOG §9 is about.
    assert "TOOL DISCIPLINE" in VOICE_SYSTEM_PROMPT


def test_voice_tools_need_a_live_call():
    """Called with no call bound, they must refuse rather than half-act."""
    from agent import tools

    assert tools.handle_end_call()["error"] == "no_active_call"
    assert tools.handle_transfer_to_human("test")["error"] == "no_active_call"


def test_a_bound_call_is_visible_to_the_tools():
    from agent import callctx

    token = callctx.bind("966500000001", "voice", "CALL-1")
    try:
        assert callctx.call_id() == "CALL-1"
        assert callctx.is_voice()
    finally:
        callctx.reset(token)
    assert callctx.call_id() is None, "the binding must not leak"


# ------------------------------------------------------------------ speech
def test_synthesis_language_follows_the_sentence():
    """Pinning the synthesizer to Arabic mangles an English reply, and the
    agent mirrors whatever language the caller used."""
    from voice import speech

    base = {"params": {"extra_body": {"num_step": 16}}}
    ar = speech.tts_config_for("كيف اقدر اخدمكم؟", base)
    en = speech.tts_config_for("How can I help you today?", base)
    assert ar["params"]["extra_body"]["language"] == "ars"
    assert en["params"]["extra_body"]["language"] == "eng"
    # …and the caller's own setting is preserved either way
    assert ar["params"]["extra_body"]["num_step"] == 16
    assert base["params"]["extra_body"] == {"num_step": 16}, "no mutation"


def test_spoken_arabic_digits_become_a_dialable_number():
    """A caller reads their number out; storing the words gives the team a
    lead nobody can ring."""
    from voice import digits

    out = digits.spoken_to_digits("رقمي صفر خمسة تسعة اربعة ستة اربعة تسعة اثنين ستة واحد")
    assert "0594" in out.replace(" ", "")


def test_eastern_arabic_numerals_are_normalised():
    from voice import digits

    assert digits.phone_digits("٠٥٩٤٦٤٩٢٦١") == "0594649261"


# ------------------------------------------- an abandoned turn must not poison
def test_consecutive_user_turns_are_merged():
    """A run of user messages with no answer between them means earlier
    turns were abandoned. Sent to the model as-is it reads as a
    conversation the agent kept ignoring, and the replies degrade until it
    stops answering usefully — which is what a caller experiences as "it
    just stopped responding"."""
    from agent.llm import _merge_orphaned_user_turns

    merged = _merge_orphaned_user_turns([
        {"role": "system", "content": "s"},
        {"role": "user", "content": "check my number"},
        {"role": "user", "content": "I want to register"},
        {"role": "user", "content": "what can you do"},
        {"role": "assistant", "content": "sure"},
    ])
    roles = [m["role"] for m in merged]
    assert roles == ["system", "user", "assistant"]
    assert "check my number" in merged[1]["content"]
    assert "what can you do" in merged[1]["content"]


def test_a_normal_conversation_is_left_alone():
    from agent.llm import _merge_orphaned_user_turns

    convo = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]
    assert _merge_orphaned_user_turns(convo) == convo


def test_tool_messages_are_not_merged():
    """Merging must never join an assistant tool_calls message to the tool
    results answering it — that pairing is what stops the agent inventing
    confirmations (WORKLOG §9)."""
    from agent.llm import _merge_orphaned_user_turns

    convo = [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "1", "type": "function",
                         "function": {"name": "get_file", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "{}"},
        {"role": "tool", "tool_call_id": "2", "content": "{}"},
    ]
    assert _merge_orphaned_user_turns(convo) == convo


# ---------------------------------------------- numbers read out in fragments
def test_a_punctuated_number_fragment_is_still_held():
    """STT punctuates what it hears, so a turn that stopped mid-number comes
    back as "The number is 9678." — with a full stop after the digits.

    Matching digits at the end of the string then never fires, the fragment
    is answered on its own, and the caller lands in the loop this exists to
    prevent: agent asks for the number, caller reads part of it, agent says
    that is not a complete number, repeat. Seen on a real call.
    """
    from voice import digits, speech

    # Through clean_transcript first, as the transport does: spoken number
    # words are digits by the time this check runs. `expecting` is set
    # because the agent has just asked for the number — which is the only
    # situation in which any of these arrive.
    for fragment in ("The number is 9678.", "342.", "رقمي صفر خمسة تسعة.",
                     "It's nine six four eight!"):
        cleaned = speech.clean_transcript(fragment)
        assert digits.unfinished_number(cleaned, expecting=True), \
            f"should hold: {fragment!r} -> {cleaned!r}"


def test_a_fragment_trailing_off_into_filler_is_still_held():
    """Stripping the punctuation was not enough: callers do not stop cleanly.

    "zero one seven one two, okay?" — the filler sits between the digits and
    the end of the string, so the tail test misses the fragment underneath
    it and the caller is back in the same loop, one word later.
    """
    from voice import digits, speech

    for fragment in ("My number is zero one seven one two, okay",
                     "It's 0171 2, yeah", "رقمي صفر واحد سبعة واحد، يعني",
                     "zero one seven one two please"):
        cleaned = speech.clean_transcript(fragment)
        assert digits.unfinished_number(cleaned, expecting=True), \
            f"should hold: {fragment!r} -> {cleaned!r}"


def test_a_complete_number_is_answered_immediately():
    """Holding a number that is already whole adds a needless pause."""
    from voice import digits

    # "0548 900 567," — a whole number that STT punctuated and grouped.
    for whole in ("0548900567", "My number is 0548900567.",
                  "رقمي 0501234567", "0548 900 567,", "01712345678"):
        assert not digits.unfinished_number(whole, expecting=True), \
            f"should not hold: {whole!r}"


def test_ordinary_speech_is_never_held():
    """A sentence that merely mentions a small number is not a phone number
    being dictated — holding it would add 2.5s to an ordinary turn."""
    from voice import digits

    for sentence in ("I want to register.", "نعم من فضلك",
                     "Yes, that is correct."):
        assert not digits.unfinished_number(sentence, expecting=True)


def test_an_ordinary_numeric_answer_is_not_mistaken_for_half_a_number():
    """"My monthly income is 4000" ends in four digits, and the first
    version of this check held every such answer.

    The cost is not only the 2.5 s: anything the caller says inside that
    pause is spliced onto it and re-transcribed as one utterance, so an
    income figure lands in the middle of the next answer.
    """
    from voice import digits

    for answer in ("My monthly income is 4000", "I was born in 1985",
                   "دخلي الشهري 4000", "سنة الميلاد 1985"):
        assert not digits.unfinished_number(answer), \
            f"should not hold: {answer!r}"


def test_the_agents_question_is_what_decides_a_number_is_coming():
    """Holding is only right when a long number was actually asked for.

    Narrow on purpose: the nouns for numbers a caller *dictates*, not the
    ones the agent reads back to them (رقم الملف, رقم الطلب) — otherwise
    every turn after a file number was announced starts holding.
    """
    from voice import digits

    for asked in ("ممكن رقم جوالكم؟", "وش رقم الهوية الوطنية؟",
                  "What is your phone number?", "ايش رقم الايبان؟"):
        assert digits.asks_for_a_long_number(asked), asked
    for not_asked in ("تم إنشاء ملفكم برقم كي واي 4029", "وش سنة الميلاد؟",
                      "Your request number is SR-5020", "كيف اقدر اخدمكم؟"):
        assert not digits.asks_for_a_long_number(not_asked), not_asked


# ------------------------------------------- the caller's number is not spoken
def test_the_caller_id_is_given_to_the_agent_on_a_call():
    """The ANI arrives with the INVITE, before anyone speaks, and is the one
    value on the call that speech recognition cannot get wrong.

    The agent asked for it anyway — "Could you please provide your phone
    number?", verbatim, on a live call — and then had to reassemble it from
    a caller reading digits in groups. Telling it plainly that the number is
    already in hand is what removes that whole exchange.
    """
    from agent.llm import caller_line

    line = caller_line("966501234567", "voice")
    assert "966501234567" in line
    assert "لا تسأل" in line, "must forbid asking for it, not merely offer it"

    # WhatsApp already shows the number in the message header; the phone
    # rule is about a caller being asked to *say* it.
    assert caller_line("966501234567", "whatsapp") == ""


def test_an_extension_is_not_offered_as_the_callers_number():
    """On the FreeSWITCH rig the ANI is `1000`. Telling the agent to file a
    family under an extension would be worse than asking them."""
    from agent.llm import caller_line

    for ani in ("1000", "1001", "", "12"):
        line = caller_line(ani, "voice")
        assert "غير متاح" in line, f"{ani!r} should not be offered as a phone"


def test_tools_fall_back_to_the_number_the_call_came_from():
    """The model should not have to carry the caller's number through the
    conversation — the same reasoning as callctx and `call_id`."""
    from agent import callctx
    from agent.tools import _phone_or_caller

    token = callctx.bind("966501234567", "voice", "CALL-1")
    try:
        assert _phone_or_caller("") == "966501234567"
        # …but a number the caller explicitly asked to register instead is
        # never overridden.
        assert _phone_or_caller("0559998888") == "0559998888"
    finally:
        callctx.reset(token)


# ------------------------------------- the agent must not answer its own voice
def test_a_one_letter_transcript_is_not_a_turn():
    """STT never reports "I heard nothing" — handed a scrap of the agent's
    own voice from a speaker it returns the nearest word.

    A live browser session transcribed "Lo" and "I" out of the agent's own
    reply and answered both, which is how a conversation with nobody in it
    starts.
    """
    from voice import speech

    for noise in ("Lo", "I", "a", ".", " ", "،"):
        assert not speech.is_meaningful_turn(noise), noise
    # …without deafening it to the short answers people really give
    for real in ("Yes.", "No", "نعم", "لا", "ok", "Comfortable",
                 "I want to register", "07", "0171"):
        assert speech.is_meaningful_turn(real), real


def test_the_browser_echo_gate_stays_shut_while_audio_is_playing():
    """The WebSocket hands over several seconds of audio in milliseconds.

    `_speaking` was cleared as soon as the last byte was *sent*, so for
    almost the whole time the visitor could hear the agent the gate was
    open and the microphone was free to pick it up. What matters is when
    the browser will have finished *playing*.
    """
    from voice.webvoice import VoiceSession

    s = VoiceSession({"phone": "966500000000"})
    assert not s.bot_speaking()
    s.queue_playback(2.0)
    assert s.bot_speaking(), "sending is not the same as finished playing"
    first = s._speaking_until
    s.queue_playback(2.0)
    assert s._speaking_until > first, "chunks queue, they do not overwrite"
    s.stop_playback()
    assert not s.bot_speaking(), "a barge-in must reopen the gate"


def test_a_missed_utterance_escalates_instead_of_going_silent():
    """The rate limit on "didn't catch that" had one failure mode: silence.

    On a real call the third consecutive miss landed inside the 12 s window,
    nothing was said, and the caller listened to a live line with nobody on
    it for 27 seconds before hanging up. Being repetitive is a far smaller
    problem than seeming to have gone away.
    """
    from voice.transport.kayan import KayanVoiceTransport as K

    said = []
    t = object.__new__(K)
    t._turns = ["agent: How can I help you today?"]
    t._misses = 0
    t._last_retry_step = -1
    t._last_retry_prompt = 0.0
    t.say = said.append

    for _ in range(3):
        t._misses += 1
        t._say_didnt_catch()

    assert len(said) == 3, "every miss must produce something audible"
    assert len(set(said)) == 3, "and not the same sentence three times"
    assert all(not any("؀" <= c <= "ۿ" for c in s) for s in said), \
        "an English caller must not be answered in Arabic"
    # By the third the agent stops insisting and offers a person.
    assert "staff" in said[-1].lower()


def test_the_retry_line_follows_the_calls_language():
    from voice.transport.kayan import KayanVoiceTransport as K

    t = object.__new__(K)
    t._turns = ["agent: كيف اقدر اخدمكم؟"]
    assert t._reply_language() == "ar"
    t._turns = ["agent: كيف اقدر اخدمكم؟", "agent: How can I help you?"]
    assert t._reply_language() == "en"
