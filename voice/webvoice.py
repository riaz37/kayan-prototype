"""Voice over a WebSocket — the same agent, reached from a browser.

Adapted from esap-voice `app/webvoice.py`. The phone path (SIP/RTP) and
this one differ only in how audio moves; the brain is `voice.brain` and the
speech calls are `voice.speech`, both shared. What lives here is the
browser-specific part: an energy VAD over 16 kHz microphone PCM, and
framing the reply audio back down the socket.

This exists because it is the fastest way to hear whether the Arabic STT,
the agent and the Arabic TTS work together — no PBX, no softphone, no
extension. It is also the demo that survives a room with no telephony.

Protocol (one socket, JSON text frames + raw binary audio):

    client -> server   binary   16 kHz mono PCM16, any chunk size
                       {"type": "stop"}            end the session

    server -> client   {"type": "state", "value": "listening"
                                                 |"thinking"|"speaking"}
                       {"type": "text",  "role": "user"|"assistant",
                        "text": ...}
                       {"type": "tool",  "name": ...}
                       {"type": "audio", "rate": 24000}   then binary…
                       {"type": "audio_end"}
                       {"type": "error", "text": ...}
"""
import asyncio
import audioop
import secrets
import time

from . import diag, digits, speech
from .brain import CallBrain
from .config import settings
from .transport.kayan import split_sentences

MIC_RATE = 16000
FRAME_MS = 20
FRAME_BYTES = MIC_RATE // 1000 * FRAME_MS * 2      # 640 bytes = 20 ms

# Browsers apply echo cancellation and noise suppression, so the levels are
# cleaner than a phone line and a lower speech threshold is safe.
SPEECH_RMS = 500
# But "the browser cancels the echo" is only true for audio the browser
# believes it is rendering, and it is never true for what leaks acoustically
# from a speaker at volume. On a laptop with the speakers up, the microphone
# hears the agent, the VAD opens an utterance on it, and the agent answers
# its own voice: a real session transcribed "Lo" and "I" out of its own
# reply and treated both as turns. So the phone path's echo gate applies
# here too — while the bot's audio is playing, only clearly-louder-than-echo
# audio opens an utterance.
BARGE_IN_RMS = 1400
# …and the browser keeps playing for a moment after the last byte lands.
ECHO_HANGOVER = 0.4
TAIL_RMS = 350
SPEECH_START_FRAMES = 3        # 60 ms of voice opens an utterance
END_SILENCE_FRAMES = 30        # 600 ms of quiet closes it
PREROLL_FRAMES = 15            # 300 ms kept from before the onset
MIN_UTTER_FRAMES = 10          # ignore blips under 200 ms
MAX_UTTER_SEC = 25
SESSION_TTL = 15 * 60          # unopened sessions expire
NUMBER_PAUSE = 2.5
# Past this the joined audio is longer than anyone spends dictating a
# number; waiting further is dead air. Same reasoning as the phone path.
MAX_HELD_SEC = 18

# Browser sessions still need a phone number: that is what the agent keys a
# conversation on, and what the backend looks a beneficiary up by. The
# console sends one so a demo can run as a real seeded beneficiary.
DEFAULT_TEST_PHONE = "966500000000"


class VoiceSession:
    """One browser conversation: VAD -> STT -> agent -> TTS -> socket."""

    def __init__(self, config: dict):
        self.config = config or {}
        self.created = time.monotonic()
        self.opened = False
        self.phone = str(self.config.get("phone") or DEFAULT_TEST_PHONE)
        self.brain = CallBrain(phone=self.phone, direction="inbound")
        self.stt = settings.stt_config()
        self.tts = settings.tts_config()
        self._stt_client = None
        self._tts_client = None
        # VAD state
        self._voiced = 0
        self._silent = 0
        self._capturing = False
        self._preroll = []
        self._utter = bytearray()
        self._voiced_frames = 0
        self._pending = bytearray()           # partial 20 ms frame
        self._speaking = False                # bot audio is going out
        self._cancel = False                  # barge-in cancels the reply
        # When the browser will have finished PLAYING what we sent, which is
        # not when we finished sending it. A WebSocket takes a few
        # milliseconds to hand over several seconds of audio, so `_speaking`
        # went False almost immediately and the echo gate was open for
        # nearly the whole time the visitor could hear the agent.
        self._speaking_until = 0.0

    # ---------- clients ----------

    def _clients(self):
        if self._stt_client is None:
            self._stt_client = speech.make_client(self.stt)
        if self._tts_client is None:
            self._tts_client = speech.make_client(self.tts)
        return self._stt_client, self._tts_client

    # ---------- microphone ----------

    def feed(self, chunk: bytes):
        """Buffer mic audio; returns a finished utterance or None."""
        self._pending += chunk
        finished = None
        while len(self._pending) >= FRAME_BYTES:
            frame = bytes(self._pending[:FRAME_BYTES])
            del self._pending[:FRAME_BYTES]
            done = self._frame(frame)
            if done is not None:
                finished = done
        return finished

    def bot_speaking(self) -> bool:
        """Is the visitor still hearing the agent right now?"""
        return time.monotonic() < self._speaking_until

    def queue_playback(self, seconds: float) -> None:
        """Note that `seconds` more audio has been handed to the browser.

        Chunks queue up and play back to back, so this accumulates rather
        than overwrites — three sentences sent in one turn are heard as one
        stretch of speech, and the gate has to stay shut for all of it.
        """
        now = time.monotonic()
        self._speaking_until = max(now, self._speaking_until) + seconds

    def stop_playback(self) -> None:
        self._speaking_until = 0.0

    def _frame(self, frame: bytes):
        rms = audioop.rms(frame, 2)
        if not self._capturing:
            self._preroll.append(frame)
            del self._preroll[:-PREROLL_FRAMES]
            # While the agent is audible, only something clearly louder than
            # the echo counts as the visitor speaking.
            threshold = BARGE_IN_RMS if self.bot_speaking() else SPEECH_RMS
            if rms >= threshold:
                self._voiced += 1
                if self._voiced >= SPEECH_START_FRAMES:
                    if self.bot_speaking():
                        # Barge-in: the visitor talked over the reply.
                        self._cancel = True
                        self.stop_playback()
                    self._capturing = True
                    self._silent = 0
                    self._voiced_frames = self._voiced
                    self._utter = bytearray(b"".join(self._preroll))
            else:
                self._voiced = 0
            return None
        self._utter += frame
        if rms >= TAIL_RMS:
            self._silent = 0
            self._voiced_frames += 1
        else:
            self._silent += 1
        too_long = len(self._utter) >= MAX_UTTER_SEC * MIC_RATE * 2
        if self._silent >= END_SILENCE_FRAMES or too_long:
            utter = bytes(self._utter)
            voiced = self._voiced_frames
            self._capturing = False
            self._voiced = self._silent = self._voiced_frames = 0
            self._preroll.clear()
            self._utter = bytearray()
            if voiced >= MIN_UTTER_FRAMES:
                return utter
            diag.log(f"webvoice: dropped {voiced}-frame blip")
        return None

    # ---------- a turn ----------

    def transcribe(self, pcm: bytes) -> str:
        stt_client, _ = self._clients()
        return speech.transcribe(stt_client, self.stt, pcm, MIC_RATE)

    def synthesize(self, text: str):
        _, tts_client = self._clients()
        return speech.synthesize(
            tts_client, speech.tts_config_for(text, self.tts), text)

    def opening(self) -> str:
        """Open the call session and return the greeting."""
        return self.brain.start()

    def close(self, duration_sec: int = 0) -> None:
        try:
            self.brain.end(outcome=self.brain.outcome(),
                           duration_sec=duration_sec)
        except Exception as e:
            diag.log(f"webvoice: logging the session failed: {e!r}")
        finally:
            self.brain.close()


class SessionStore:
    """Short-lived voice sessions, minted over HTTP and opened once."""

    def __init__(self):
        self._sessions = {}

    def create(self, config: dict) -> str:
        self._prune()
        session_id = secrets.token_urlsafe(24)
        self._sessions[session_id] = VoiceSession(config)
        return session_id

    def take(self, session_id: str):
        """Claim a session. Single use: a second opener gets nothing."""
        self._prune()
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.opened = True
        return session

    def drop(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _prune(self) -> None:
        now = time.monotonic()
        for key in [
            k for k, s in self._sessions.items()
            if not s.opened and now - s.created > SESSION_TTL
        ]:
            self._sessions.pop(key, None)


async def run_socket(ws, session) -> None:
    """Drive one open browser conversation until the socket closes."""
    loop = asyncio.get_running_loop()
    started = time.monotonic()

    async def say(text: str):
        """Speak one chunk of the reply, unless barged in on."""
        if not text.strip():
            return
        session._speaking = True
        session._cancel = False
        try:
            pcm, rate = await loop.run_in_executor(
                None, session.synthesize, text)
        except Exception as e:
            diag.log(f"webvoice: TTS failed: {e!r}")
            session._speaking = False
            return
        if session._cancel:
            session._speaking = False
            return
        await ws.send_json({"type": "audio", "rate": rate})
        # ~100 ms per message keeps barge-in responsive.
        step = rate // 10 * 2
        sent = 0
        for i in range(0, len(pcm), step):
            if session._cancel:
                break
            await ws.send_bytes(pcm[i:i + step])
            sent += len(pcm[i:i + step])
        await ws.send_json({"type": "audio_end"})
        # Shut the echo gate for as long as the browser will be PLAYING
        # this, plus a moment for its own buffering — not merely for as
        # long as it took to send, which is milliseconds.
        session.queue_playback(sent / 2 / rate + ECHO_HANGOVER)
        session._speaking = False

    # Set when the agent's last reply asked for a phone number or an ID —
    # the signal that a turn ending in a few digits is half of one rather
    # than an ordinary answer. Same rule as the phone transport.
    expecting_number = False

    async def handle(text: str):
        """One turn: stream the agent's reply, speaking as sentences land."""
        nonlocal expecting_number
        await ws.send_json({"type": "state", "value": "thinking"})
        # The brain's turn() is a blocking generator (httpx streaming), so
        # it is drained on the executor and handed over one event at a
        # time; awaiting inside the generator would block the event loop
        # and stall every other socket.
        queue: asyncio.Queue = asyncio.Queue()

        def drain():
            try:
                for event in session.brain.turn(text):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, drain)

        buf, spoken, said_state = "", "", False
        while True:
            event = await queue.get()
            if event is None:
                break
            kind, value = event
            if kind == "text":
                buf += value
                ready, buf = split_sentences(buf, 4 if not spoken else 24)
                for sentence in ready:
                    spoken += sentence + " "
                    if not said_state:
                        said_state = True
                        await ws.send_json({"type": "state",
                                            "value": "speaking"})
                    await ws.send_json({"type": "text", "role": "assistant",
                                        "text": sentence})
                    await say(sentence)
            elif kind == "reset":
                buf, spoken = "", ""
                await ws.send_json({"type": "reset"})
            elif kind == "tool":
                await ws.send_json({"type": "tool", "name": value})
            elif kind == "done":
                tail = buf.strip()
                if tail:
                    await ws.send_json({"type": "text", "role": "assistant",
                                        "text": tail})
                    await say(tail)
                    spoken += tail
                elif not spoken.strip() and value:
                    await ws.send_json({"type": "text", "role": "assistant",
                                        "text": value})
                    await say(value)
            elif kind == "error":
                await ws.send_json({"type": "error", "text": value})
                await say(value)
        expecting_number = digits.asks_for_a_long_number(spoken)
        await ws.send_json({"type": "state", "value": "listening"})

    # Greet first, exactly as a call does.
    try:
        first = await loop.run_in_executor(None, session.opening)
    except Exception as e:
        diag.log(f"webvoice: opening failed: {e!r}")
        first = ""
    if first:
        await ws.send_json({"type": "text", "role": "assistant",
                            "text": first})
        await ws.send_json({"type": "state", "value": "speaking"})
        await say(first)
    await ws.send_json({"type": "state", "value": "listening"})

    # A caller reading a number pauses between groups, which closes the
    # utterance mid-number. The AUDIO is held and re-transcribed with the
    # rest joined on: half a number on its own transcribes far worse than
    # the whole thing does.
    held, held_audio, held_until = "", b"", 0.0

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") is not None:
                if '"stop"' in message["text"]:
                    break
                continue
            chunk = message.get("bytes")
            if not chunk:
                continue
            was_cancelled = session._cancel
            utter = session.feed(chunk)
            if session._cancel and not was_cancelled:
                # Barge-in. The browser has already been handed audio it
                # has not played yet, and it will keep playing it into the
                # microphone unless told to drop it — the phone path flushes
                # its playout buffer for the same reason.
                await ws.send_json({"type": "flush"})
            if utter is None:
                if held and time.monotonic() > held_until:
                    # Nothing more came; answer what we have.
                    text, held, held_audio = held, "", b""
                    await ws.send_json({"type": "text", "role": "user",
                                        "text": text})
                    await handle(text)
                continue
            if held_audio:
                utter = held_audio + utter
            try:
                text = await loop.run_in_executor(
                    None, session.transcribe, utter)
            except Exception as e:
                diag.log(f"webvoice: STT failed: {e!r}")
                continue
            text = (text or "").strip()
            if not text:
                diag.log(f"webvoice: empty transcript "
                         f"({len(utter) / 2 / MIC_RATE:.1f}s)")
                continue
            if not speech.is_meaningful_turn(text):
                # Almost always the agent's own voice through the speaker.
                diag.log(f"webvoice: ignoring {text!r} — too short to be "
                         "a turn")
                continue
            held_sec = len(utter) / 2 / MIC_RATE
            if (digits.unfinished_number(text, expecting_number)
                    and held_sec < MAX_HELD_SEC):
                held, held_audio = text, utter
                held_until = time.monotonic() + NUMBER_PAUSE
                diag.log(f"webvoice: {text[-24:]!r} looks like half a "
                         f"number ({held_sec:.1f}s held) — waiting for "
                         "the rest")
                continue
            held, held_audio = "", b""
            await ws.send_json({"type": "text", "role": "user", "text": text})
            await handle(text)
    finally:
        session.close(duration_sec=int(time.monotonic() - started))
