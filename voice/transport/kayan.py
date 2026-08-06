"""The voice transport: caller audio in, Kayan's agent, speech out.

Adapted from esap-voice `app/transport/cascade.py`. The audio half is
theirs and is kept close to verbatim — the energy VAD, the barge-in and
echo handling, the sentence chunking that gets the first words out while
the rest is still being generated, the greeting cache, the WAV dumps of
utterances STT heard nothing in. All of that was tuned on live calls.

The thinking half is gone. Where cascade called an LLM, held its own
message history and ran its own tools, this asks `voice.brain.CallBrain`
for a turn and speaks what comes back. See brain.py for why.

Per caller turn:
  1. Energy VAD segments caller speech into an utterance (with pre-roll).
  2. The utterance goes to STT as a 16 kHz WAV.
  3. The transcript goes to the agent, which streams its reply back.
  4. Streamed text is cut at sentence boundaries and each sentence is
     synthesized as it completes, so the caller hears the answer begin
     about a second before it has finished being written.
  5. If the caller talks over the agent (louder than the echo gate), the
     turn is cancelled and playout flushed.
"""
import audioop
import queue
import threading
import time
import wave

from .. import diag
from .. import digits
from .. import speech
from ..audio import RATE
from ..config import settings
from .ai_base import AiAudioBridge, BARGE_IN_RMS

# --- energy VAD (20 ms frames) ---
SPEECH_RMS = 600          # 16-bit RMS that counts as speech when bot is idle
TAIL_RMS = 400            # quieter than this counts toward end-of-utterance
SPEECH_START_FRAMES = 3   # 60 ms above threshold to open an utterance
TAIL_KEEP_FRAMES = 10     # trailing silence kept for STT (rest is trimmed)
PREROLL_FRAMES = 15       # 300 ms kept from before speech onset
MIN_UTTER_FRAMES = 10     # ignore blips shorter than 200 ms of speech
MAX_UTTER_SEC = 20        # hard cap per utterance
# Only ever applied to a turn that ended mid-number (see voice/digits.py).
NUMBER_PAUSE = 2.5
# A caller reading a long number in short groups re-holds each time, and
# every hold re-transcribes the whole thing from the start. Past this the
# joined audio is longer than anyone dictates a number for, the STT round
# trip is no longer cheap, and continuing to wait is just dead air.
MAX_HELD_SEC = 18

# --- sentence chunking for incremental TTS ---
MIN_TTS_CHARS = 24        # don't synthesize fragments shorter than this...
FIRST_TTS_CHARS = 4       # ...except the very first chunk of a reply, which
                          # goes out as soon as any sentence completes
MAX_TTS_CHARS = 300       # force a split on run-on text
# Arabic full stop and question mark are their own code points; a reply that
# ends "؟" must be a sentence boundary or the caller waits for the whole
# paragraph before hearing anything.
_ENDERS = ".!?…\n۔؟"

# One short word while a tool runs. Without it a tool round is several
# seconds of dead air and callers say "hello? are you there?".
FILLER_AR = "لحظة"

# The agent's own tool names that control the call. Imported lazily so the
# engine can run without the agent package importable (e.g. in tests).
CALL_CONTROL = ("transfer_to_human", "end_call")

# The configured greeting is the same audio on every call — synthesize it
# once and replay it, so from the second call on the caller hears it the
# instant the call is answered (no TTS round trip).
_greeting_cache: dict = {}


def split_sentences(buf: str, min_chars: int = MIN_TTS_CHARS):
    """Split streamed reply text into (ready-to-speak chunks, remainder)."""
    ready = []
    while True:
        cut = -1
        for i, ch in enumerate(buf):
            if ch not in _ENDERS or i + 1 < min_chars:
                continue
            # "3.5" / "example.com": a period must be followed by
            # whitespace already present in the buffer to count.
            if ch == "." and (i + 1 >= len(buf) or not buf[i + 1].isspace()):
                continue
            cut = i
            break
        if cut == -1:
            if len(buf) >= MAX_TTS_CHARS:
                sp = buf.rfind(" ", min_chars, MAX_TTS_CHARS)
                cut = sp if sp > 0 else MAX_TTS_CHARS - 1
            else:
                break
        chunk = buf[:cut + 1].strip()
        if chunk:
            ready.append(chunk)
        buf = buf[cut + 1:]
        min_chars = MIN_TTS_CHARS
    return ready, buf


def _norm(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


def already_said(spoken: str, text: str) -> bool:
    """Has this sentence already gone out this turn?"""
    if not spoken or not text:
        return False
    said, fresh = _norm(spoken), _norm(text)
    return fresh in said or said.endswith(fresh)


class KayanVoiceTransport(AiAudioBridge):
    TAG = "kayan"

    RETRY_PROMPT_GAP = 12.0   # min seconds between "didn't catch that"s

    # What to say when STT returns nothing for an utterance the VAD was sure
    # contained speech. It escalates, because repeating the same sentence at
    # someone the recogniser cannot hear is how a call dies: on a real call
    # the caller's name came back empty three times, and the third time the
    # rate limit suppressed the prompt entirely and the line went silent for
    # 27 seconds. Silence is the one response that tells the caller nothing.
    DIDNT_CATCH = {
        "ar": ["عذرا، ما سمعتكم زين. ممكن تعيدون؟",
               "لسه ما وصلني صوتكم واضح. ممكن تقربون من السماعة وتعيدون؟",
               "يبدو ان الصوت ما يوصلني زين. تبون احولكم لأحد الموظفين؟"],
        "en": ["Sorry, I didn't catch that. Could you say it again?",
               "I still can't hear you clearly. Could you move closer to "
               "the microphone and try once more?",
               "The line doesn't seem to be carrying your voice. Would you "
               "like me to put you through to a member of staff?"],
    }

    def __init__(self, call, brain, stt: dict = None, tts: dict = None):
        super().__init__(call)
        self._vad_lock = threading.Lock()
        self._last_frame_at = 0.0
        self.brain = brain
        self.stt = stt or settings.stt_config()
        self.tts = tts or settings.tts_config()
        self.greeting = ""
        self._utter_q = queue.Queue()
        self._gen = 0                 # bumped on barge-in to cancel a turn
        self._end_after_turn = False  # end_call / transfer tool was invoked
        self._transfer_to = None
        self._last_retry_prompt = 0.0  # "didn't catch that" rate limit
        self._last_retry_step = -1     # which line of DIDNT_CATCH was last
        self._misses = 0               # consecutive utterances STT lost
        self._stt_miss_saved = 0       # wav dumps of failed utterances
        self._held = ""                # half a number, waiting for the rest
        self._held_audio = b""
        self._held_until = 0.0
        # Set when the agent's last reply asked the caller to read out a
        # phone number or an ID. Without it every numeric answer is treated
        # as half a number and costs the caller a NUMBER_PAUSE.
        self._expecting_number = False
        self._fail_count = 0
        self._notes = []               # facts for the agent's next turn
        self._turns = []               # transcript, for the call log
        self._stt_client = None
        self._tts_client = None
        # End-of-utterance silence, in 20 ms frames.
        self._end_silence_frames = max(
            8, int(settings.end_silence_seconds / 0.02))
        # VAD state
        self._voiced = 0
        self._silent = 0
        self._capturing = False
        self._preroll = []
        self._utter = bytearray()
        self._voiced_frames = 0

    # ---------- lifecycle ----------

    def start(self) -> None:
        super().start()
        threading.Thread(target=self._worker, daemon=True,
                         name="kayan-voice-worker").start()

    def transcript(self) -> str:
        """The call as text, for POST /voice/call-end."""
        return "\n".join(self._turns)

    # ---------- caller -> VAD -> utterance queue ----------

    def _handle_caller_frame(self, pcm16: bytes) -> None:
        with self._vad_lock:
            self._last_frame_at = time.monotonic()
            self._vad_frame(pcm16)

    def _idle_check(self) -> None:
        """Close an utterance when the caller's audio simply STOPS.

        The VAD ends a turn by counting quiet frames, which assumes a
        continuous stream of them. That assumption does not hold: FreeSWITCH
        sends nothing at all during `silence_stream`, and real telephony
        does the same thing for a different reason — silence suppression,
        where a phone or carrier stops transmitting between words and sends
        comfort noise instead. Either way the frames stop arriving, the
        quiet-frame counter never advances, and the utterance stays open
        forever: the caller speaks and the agent never answers.

        So the turn also ends on a wall clock. Called from the worker loop.
        """
        with self._vad_lock:
            if not self._capturing or not self._last_frame_at:
                return
            idle = time.monotonic() - self._last_frame_at
            if idle < settings.end_silence_seconds:
                return
            diag.log(f"voice: caller audio stopped for {idle:.2f}s — "
                     "closing the utterance")
            # No trailing silence arrived, so there is nothing to trim.
            self._finish_utterance(trim=False)

    @staticmethod
    def _is_dc_rail(pcm16: bytes) -> bool:
        """A constant-value frame — never speech, always an artefact.

        When RTP resumes after a gap, pyVoIP hands over a few frames of a
        single repeated sample, which converts to full-scale DC (RMS 32768,
        louder than anything a person can say). The VAD reads that as the
        caller shouting: it opens an utterance, and mid-reply it fires a
        barge-in that cuts the agent off. Real speech is never one value
        repeated 160 times.
        """
        lo, hi = audioop.minmax(pcm16, 2)
        return lo == hi

    def _vad_frame(self, pcm16: bytes) -> None:
        if self._is_dc_rail(pcm16):
            return
        rms = audioop.rms(pcm16, 2)
        if not self._capturing:
            self._preroll.append(pcm16)
            del self._preroll[:-PREROLL_FRAMES]
            # While the bot is speaking, only clearly-louder-than-echo audio
            # opens an utterance.
            threshold = BARGE_IN_RMS if self._bot_speaking() else SPEECH_RMS
            if rms >= threshold:
                self._voiced += 1
                if self._voiced >= SPEECH_START_FRAMES:
                    if self._bot_speaking():
                        self._barge_in()
                    self._capturing = True
                    self._silent = 0
                    self._voiced_frames = self._voiced
                    self._utter = bytearray(b"".join(self._preroll))
            else:
                self._voiced = 0
        else:
            self._utter += pcm16
            if rms >= TAIL_RMS:
                self._silent = 0
                self._voiced_frames += 1
            else:
                self._silent += 1
            if (self._silent >= self._end_silence_frames
                    or len(self._utter) >= MAX_UTTER_SEC * RATE * 2):
                self._finish_utterance(
                    trim=self._silent >= self._end_silence_frames)

    def _finish_utterance(self, trim: bool) -> None:
        utter = bytes(self._utter)
        if trim:
            # Most of the endpointing silence is dead air STT doesn't need.
            utter = utter[:len(utter)
                          - (self._end_silence_frames - TAIL_KEEP_FRAMES) * 320]
        voiced = self._voiced_frames
        self._capturing = False
        self._voiced = 0
        self._voiced_frames = 0
        self._preroll.clear()
        self._utter = bytearray()
        if voiced >= MIN_UTTER_FRAMES:
            self._utter_q.put((utter, self._gen))
        else:
            diag.log(f"voice: dropped {voiced}-frame blip")
            self._resume_pending_hangup()

    def _barge_in(self) -> None:
        self._gen += 1
        self._n_interrupts += 1
        if self._end_after_turn or self.wants_hangup:
            # Interruption during the goodbye: could be a real "لحظة!" or
            # just line echo. Hold the hangup until the utterance resolves —
            # a real transcript cancels it in _turn, an empty one resumes it.
            self._hangup_hold_until = time.monotonic() + 8.0
            diag.log("voice: barge-in during pending hangup — holding "
                     "until the speech is transcribed")
        self._flush_playout()
        diag.log("voice: barge-in — flushing playout, cancelling turn")

    # ---------- talking out of band ----------

    def _say_didnt_catch(self) -> None:
        """Tell the caller we could not hear them, escalating each time.

        The rate limit this replaces existed so line noise could not turn
        into a loop, and it did its job — but its failure mode was total
        silence. On a real call the third consecutive miss fell inside the
        12 s window, nothing was said at all, and the caller sat listening
        to a live line with nobody on it until they hung up. Being repetitive
        is a much smaller problem than seeming to have gone away, so the gap
        only suppresses a repeat of the *same* line; a new one always goes
        out, and by the third the agent stops insisting and offers a human.

        The line follows the conversation's language. This used to be
        hardcoded Arabic, so an English caller who was not understood was
        then answered in a language they had not used — which reads as the
        system breaking, exactly when they are already unsure.
        """
        lines = self.DIDNT_CATCH.get(self._reply_language()) or \
            self.DIDNT_CATCH["ar"]
        step = min(self._misses, len(lines)) - 1
        now = time.monotonic()
        if step == self._last_retry_step and \
                now - self._last_retry_prompt < self.RETRY_PROMPT_GAP:
            diag.log("voice: same retry line was just said — staying quiet")
            return
        self._last_retry_prompt = now
        self._last_retry_step = step
        self.say(lines[step])

    def _reply_language(self) -> str:
        """Which language this call is being conducted in.

        Read off the last thing the agent said, which is the agent's own
        decision about the caller's language and therefore the one that
        keeps the call consistent.
        """
        for turn in reversed(self._turns):
            if turn.startswith("agent: "):
                return "ar" if speech.is_arabic(turn[7:]) else "en"
        return "ar"

    def say(self, text: str) -> None:
        """Speak a line the agent did not generate (e.g. "the transfer
        failed"), and tell the agent it was said so its next turn does not
        contradict it."""
        self._turns.append(f"agent: {text}")
        self.note(f'You have already said this to the caller, out loud: '
                  f'"{text}". Do not repeat it.')
        self._speak(text, self._gen)

    MAX_NOTES = 5

    def note(self, text: str) -> None:
        """Tell the agent something happened, without speaking it.

        Notes ride in the system prompt for one turn, never in the message
        history — a note is not something the caller said, and injecting it
        as a user turn would make the agent answer it.
        """
        self._notes.append(text)
        del self._notes[:-self.MAX_NOTES]

    def _take_notes(self):
        notes, self._notes = self._notes, []
        return "\n".join(f"- {n}" for n in notes) if notes else None

    def _cancel_pending_hangup(self, why: str) -> None:
        if not (self._end_after_turn or self.wants_hangup):
            return
        self._end_after_turn = False
        self._transfer_to = None
        self.wants_hangup = False
        self.transfer_target = None
        self._hangup_hold_until = 0.0
        # A transfer may already be dialling the target — stop it.
        self._transfer_cancelled = True
        diag.log(f"voice: {why} — cancelled pending hangup/transfer")

    def _resume_pending_hangup(self) -> None:
        if self._end_after_turn or self.wants_hangup:
            self._hangup_hold_until = 0.0
            diag.log("voice: no real speech — pending hangup resumes")

    # ---------- pipeline worker ----------

    def _ensure_clients(self) -> None:
        if self._stt_client is None:
            self._stt_client = speech.make_client(self.stt)
        if self._tts_client is None:
            self._tts_client = speech.make_client(self.tts)

    def _worker(self) -> None:
        try:
            self._ensure_clients()
        except Exception as e:
            self.error = f"Speech setup error: {e}"
            return
        diag.log(f"voice: pipeline up — stt={self.stt.get('model')} "
                 f"tts={self.tts.get('model')}/{self.tts.get('voice')}")
        gen = self._gen
        # The greeting comes from POST /voice/call-start, so it already
        # carries the beneficiary's name when the number is known.
        try:
            self.greeting = self.brain.start()
        except Exception as e:
            diag.log(f"voice: brain.start failed ({e!r})")
            self.greeting = self.greeting or ""
        if self.greeting:
            self._speak_greeting(gen)
            self._turns.append(f"agent: {self.greeting}")
        while self._active():
            try:
                utter, gen = self._utter_q.get(timeout=0.2)
            except queue.Empty:
                # The caller may have stopped transmitting mid-utterance
                # rather than sending quiet frames — close it on time.
                self._idle_check()
                # Nothing more came: a number the caller was still reading
                # out has to be answered on its own now.
                if self._held and time.monotonic() > self._held_until:
                    text = self._held
                    self._held, self._held_audio = "", b""
                    self._respond(text, self._gen)
                continue
            if gen != self._gen:
                continue  # superseded by a barge-in
            self._turn(utter, gen)

    def _turn(self, pcm8k: bytes, gen: int) -> None:
        t0 = time.monotonic()
        if self._held_audio:
            # Half a number, waiting for the rest: transcribe the WHOLE
            # thing rather than stitching two bad fragments together.
            pcm8k = self._held_audio + pcm8k
        try:
            text = self._transcribe(pcm8k)
        except Exception as e:
            self._pipeline_failed("STT", e)
            return
        text = (text or "").strip()
        if text and not speech.is_meaningful_turn(text):
            # STT never says "I heard nothing" — given a scrap of the
            # agent's own voice coming back down the line it returns the
            # nearest word. Answering that is worse than ignoring it: the
            # agent ends up replying to itself.
            diag.log(f"voice: ignoring {text!r} — too short to be a turn")
            self._resume_pending_hangup()
            return
        if text:
            # People read a number in groups, and the pause between them
            # closes the utterance — "صفر خمسة تسعة … اربعة ستة اربعة" then
            # arrives as two turns, each transcribed on its own and each
            # wrong. Hold the first half and join the rest to it.
            held_sec = len(pcm8k) / 2 / RATE
            if (digits.unfinished_number(text, self._expecting_number)
                    and held_sec < MAX_HELD_SEC):
                self._held, self._held_audio = text, pcm8k
                self._held_until = time.monotonic() + NUMBER_PAUSE
                diag.log(f"voice: {text[-24:]!r} looks like half a "
                         f"number ({held_sec:.1f}s held) — waiting for "
                         "the rest")
                return
            self._held, self._held_audio = "", b""
        if not text:
            # The caller DID speak (the VAD only forwards utterances with
            # >=200 ms of voice) but STT heard nothing. Staying silent reads
            # as the agent going deaf, so say so.
            rms = audioop.rms(pcm8k, 2)
            secs = len(pcm8k) / 2 / RATE
            self._misses += 1
            diag.log(f"voice: empty transcript ({secs:.1f}s, rms {rms}) "
                     f"— miss {self._misses}")
            self._save_stt_miss(pcm8k)
            self._resume_pending_hangup()
            if (not (self._end_after_turn or self.wants_hangup)
                    and gen == self._gen and self._active()):
                self._say_didnt_catch()
            return
        diag.log(f"voice: caller said {text!r} "
                 f"(stt {time.monotonic() - t0:.2f}s, "
                 f"{len(pcm8k) // 320} frames)")
        # Heard them: a later bad patch starts from "sorry, say that again"
        # rather than from wherever the last one escalated to.
        self._misses = 0
        self._last_retry_step = -1
        if gen != self._gen or not self._active():
            return
        self._cancel_pending_hangup("caller spoke")
        self._respond(text, gen)

    def _respond(self, user_text: str, gen: int) -> None:
        timing = {"t0": time.monotonic(), "first": None, "audio": None}
        self._turns.append(f"caller: {user_text}")
        spoken = ""
        buf = ""
        # `spoken` is cleared by a reset; this is not. The filler exists to
        # break silence, so if the caller has already heard something this
        # turn — even a retracted preamble — a "لحظة" on top of it is one
        # sound too many.
        said_anything = False
        filler_said = False
        action = None
        note = self._take_notes()
        # Held explicitly so a barge-in can close it. Returning out of a
        # `for` over a generator only drops the reference; the HTTP stream
        # to the agent — and the LLM request behind it — keeps running,
        # and a caller who interrupts often enough starves the model.
        stream = self.brain.turn(user_text, system_note=note)
        try:
          for kind, value in stream:
            if gen != self._gen or not self._active():
                return
            if kind == "text":
                buf += value
                ready, buf = split_sentences(
                    buf,
                    FIRST_TTS_CHARS if timing["first"] is None
                    else MIN_TTS_CHARS)
                for sentence in ready:
                    if already_said(spoken, sentence):
                        continue
                    spoken += sentence + " "
                    said_anything = True
                    self._speak_timed(sentence, gen, timing)
            elif kind == "reset":
                # The agent wrote preamble and then decided to call a tool;
                # on WhatsApp the console just discards it. Out loud it has
                # already reached the caller's ear and cannot be recalled.
                # Flushing playout stops whatever has not left the buffer
                # yet — the caller may still hear a clipped half word. The
                # real fix is upstream: the voice prompt tells the agent to
                # say nothing before calling a tool.
                if buf.strip() or spoken:
                    diag.log(f"voice: reset — discarding preamble "
                             f"{(spoken + buf)[:60]!r}")
                buf, spoken = "", ""
                self._flush_playout()
            elif kind == "tool":
                if not said_anything and not filler_said:
                    filler_said = True
                    said_anything = True
                    self._speak(FILLER_AR, gen)
            elif kind == "tool_result":
                # Act on the tool's NAME only once its RESULT says it
                # worked. Hanging up or transferring because the model
                # *tried* to would drop a caller whose transfer failed —
                # the agent has just told them it could not be done.
                if value.get("name") in CALL_CONTROL:
                    if value.get("ok"):
                        action = value["name"]
                    else:
                        diag.log(f"voice: {value.get('name')} failed — "
                                 "staying on the call")
            elif kind == "done":
                tail = buf.strip()
                buf = ""
                if tail and not already_said(spoken, tail):
                    spoken += tail
                    self._speak_timed(tail, gen, timing)
                # `value` is the authoritative reply. If the stream gave us
                # nothing to say (all of it was retracted by a reset), say
                # the reply itself rather than leaving the caller in
                # silence.
                if not spoken.strip() and value:
                    spoken = value
                    for sentence in _split_all(value):
                        self._speak_timed(sentence, gen, timing)
            elif kind == "error":
                if value:
                    spoken += value
                    self._speak_timed(value, gen, timing)
                break
        finally:
            stream.close()
        spoken = spoken.strip()
        if spoken:
            self._turns.append(f"agent: {spoken}")
            self._fail_count = 0
            # If that reply asked for a phone number or an ID, the next
            # turn ending in a few digits is half of one, not an answer.
            self._expecting_number = digits.asks_for_a_long_number(spoken)
            diag.log(f"voice: agent said {spoken!r}"
                     + (" [expecting a dictated number]"
                        if self._expecting_number else ""))
        if action and not self.wants_hangup:
            self._apply_call_control(action)

    def _apply_call_control(self, action: str) -> None:
        """Act on end_call / transfer_to_human once the reply is queued.

        The controller's tick loop does the telephony, and only after the
        agent's closing words have finished playing out — hanging up the
        instant the tool returns cuts the goodbye off mid-word.
        """
        self._end_after_turn = True
        if action == "transfer_to_human":
            self._transfer_to = settings.sip_transfer_target
            self.transfer_target = self._transfer_to
            diag.log(f"voice: turn complete — transferring to "
                     f"{self._transfer_to} once speech drains")
        else:
            diag.log("voice: turn complete — hanging up once speech drains")
        self.wants_hangup = True

    # ---------- speech ----------

    def _speak_timed(self, sentence: str, gen: int, timing) -> None:
        if timing["first"] is None:
            timing["first"] = time.monotonic()
        self._speak(sentence, gen)
        if timing["audio"] is None:
            timing["audio"] = time.monotonic()
            diag.log(
                "voice: REPLY LATENCY "
                f"{timing['audio'] - timing['t0']:.2f}s from utterance end "
                f"to first audio")

    def _synthesize(self, text: str):
        """TTS one chunk; returns (mono s16 PCM, rate)."""
        return speech.synthesize(
            self._tts_client, speech.tts_config_for(text, self.tts), text)

    def _speak(self, text: str, gen: int) -> None:
        if gen != self._gen or not self._active():
            return
        t0 = time.monotonic()
        try:
            pcm, rate = self._synthesize(text)
        except Exception as e:
            self._pipeline_failed("TTS", e)
            return
        if gen != self._gen or not self._active():
            return  # barge-in while synthesizing: discard
        self._ingest_bot_audio(pcm, rate)
        self._fail_count = 0
        diag.log(f"voice: tts {len(text)} chars -> "
                 f"{len(pcm) // 2 / rate:.1f}s audio "
                 f"in {time.monotonic() - t0:.2f}s")

    def _speak_greeting(self, gen: int) -> None:
        import json as _json
        key = (self.tts.get("base_url", ""), self.tts.get("model", ""),
               self.tts.get("voice", ""),
               _json.dumps(self.tts.get("params") or {}, sort_keys=True),
               self.greeting)
        cached = _greeting_cache.get(key)
        if cached is not None:
            self._ingest_bot_audio(*cached)
            diag.log("voice: greeting from cache (0 ms)")
            return
        t0 = time.monotonic()
        try:
            pcm, rate = self._synthesize(self.greeting)
        except Exception as e:
            self._pipeline_failed("TTS", e)
            return
        # Only a greeting with no name in it is worth caching — a
        # personalised one ("حياكم الله سعد") is different every call and
        # would grow this dict without bound.
        if self.brain is None or not self.brain.identified:
            _greeting_cache[key] = (pcm, rate)
        if gen == self._gen and self._active():
            self._ingest_bot_audio(pcm, rate)
        self._fail_count = 0
        diag.log(f"voice: greeting synthesized in "
                 f"{time.monotonic() - t0:.2f}s")

    MAX_STT_MISS_DUMPS = 5

    def _save_stt_miss(self, pcm8k: bytes) -> None:
        """Dump an utterance STT heard nothing in, so "why empty?" can be
        answered by listening: real speech the model could not decode, or a
        noise blip the VAD mistook for speech."""
        if self._stt_miss_saved >= self.MAX_STT_MISS_DUMPS:
            return
        self._stt_miss_saved += 1
        try:
            diag.CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = (diag.CALL_LOG_DIR
                    / f"stt-miss-{time.strftime('%Y%m%d-%H%M%S')}.wav")
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm8k)
            diag.log(f"voice: saved the audio to {path.name}")
        except Exception as e:
            diag.log(f"voice: could not save stt miss ({e!r})")

    def _transcribe(self, pcm8k: bytes) -> str:
        return speech.transcribe(self._stt_client, self.stt, pcm8k, RATE)

    def _pipeline_failed(self, stage: str, e: Exception) -> None:
        self._fail_count += 1
        diag.log(f"voice: {stage} failed ({self._fail_count}): {e!r}")
        # One transient failure just skips a turn; repeated failures mean
        # the endpoint is misconfigured or down — surface it and end the
        # call rather than leaving the caller listening to nothing.
        if self._fail_count >= 2:
            self.error = f"{stage} error: {e}"


def _split_all(text: str):
    """Every sentence in `text`, including a trailing fragment."""
    ready, tail = split_sentences(text, FIRST_TTS_CHARS)
    if tail.strip():
        ready.append(tail.strip())
    return ready or [text]
