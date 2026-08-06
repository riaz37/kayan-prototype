"""Shared audio machinery for AI call transports (Gemini Live, cascade).

Audio path (both directions are the same for every AI transport):
  caller -> pyVoIP (8 kHz u8 PCM) -> 16-bit PCM -> provider-specific handler
  bot    -> any-rate s16 PCM -> low-pass -> 8 kHz -> G.711 -> playout queue

Timing model: pyVoIP's own RTP transmit thread is the one and only clock.
It reads one 20 ms frame from its outgoing buffer every ~20 ms and pads
with silence bytes when the buffer runs dry — so if we feed it from a
second free-running clock, the two drift and it keeps catching our frames
half-written, splicing silence into the middle of the waveform (harsh
50 Hz buzz + stutter).  Instead the feeder thread measures pyVoIP's actual
transmit backlog and tops it up to a small cushion (~120 ms), never
letting it underrun.  Barge-in stays fast: flushing the local playout
queue means at most the cushion still plays out.

Resampling uses audioop.ratecv with persistent state; downsampling to
8 kHz is preceded by a windowed-sinc low-pass (needs numpy, optional) so
energy above 4 kHz doesn't alias into the phone band.
"""
import audioop
import os
import sys
import threading
import time
import wave
from collections import deque

from pyVoIP.RTP import PayloadType
from pyVoIP.VoIP import CallState

from .. import diag
from ..audio import FRAMES, RATE, SILENCE_16, SILENCE_U8, s16_to_u8, u8_to_s16
from .base import CallTransport

try:
    import numpy as _np
except ImportError:  # filter is skipped, plain ratecv still works
    _np = None

# Latency/robustness trade-off: the cushion is added one-way latency for
# bot speech (and the residue that still plays after a barge-in flush), but
# it must outlast the worst feeder-thread scheduling stall.  With the 1 ms
# multimedia timer and a 2 ms GIL switch interval, measured stalls stay
# well under 100 ms; 6 frames = 120 ms holds without underruns.
CUSHION_FRAMES = 6

# Echo gate: phones leak the bot's own voice back down the line (acoustic
# echo), and speech detection hears it as the caller interrupting — flushing
# our playout and chopping the bot off mid-sentence.  While the bot is
# speaking, only treat caller audio as speech when it is clearly louder than
# echo; a real interruption ("hey, stop") passes, the echo floor doesn't.
BARGE_IN_RMS = 1500      # 16-bit RMS a frame must exceed to count as speech
ECHO_GATE_HANGOVER = 0.4  # keep gating this long after the last bot frame

# TTS voices speak near full scale; G.711 telephony expects a hotter-than-
# that signal to be rare, and sensitive earpieces / carrier limiters distort
# on it.  -6 dB puts the bot at a normal talker level.
OUTPUT_GAIN = 0.5


def _win_timer_resolution(enable: bool) -> None:
    """time.sleep on Windows is ~15.6 ms granular by default, which wrecks
    20 ms audio loops (ours and pyVoIP's).  Ask for 1 ms while on a call."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        if enable:
            ctypes.windll.winmm.timeBeginPeriod(1)
        else:
            ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass


class _AntiAliasFilter:
    """33-tap windowed-sinc low-pass (3.4 kHz cutoff at the source rate),
    streamed with overlap state, applied before decimation to 8 kHz."""

    TAPS = 33

    def __init__(self, in_rate: int = 24000):
        if _np is None or in_rate <= 2 * 3400:
            self._h = None
            return
        n = _np.arange(self.TAPS) - (self.TAPS - 1) / 2
        h = _np.sinc(2 * 3400 / in_rate * n) * _np.hamming(self.TAPS)
        self._h = h / h.sum()
        self._tail = _np.zeros(self.TAPS - 1)

    def process(self, pcm: bytes) -> bytes:
        if self._h is None or not pcm:
            return pcm
        x = _np.frombuffer(pcm, dtype=_np.int16).astype(_np.float64)
        x = _np.concatenate((self._tail, x))
        y = _np.convolve(x, self._h, mode="valid")
        self._tail = x[-(self.TAPS - 1):]
        return _np.clip(y, -32768, 32767).astype(_np.int16).tobytes()


class AiAudioBridge(CallTransport):
    """Base for AI transports: owns the caller-audio RX loop, the paced
    playout feeder, echo gating, and full-precision G.711 encoding.

    Subclasses implement ``_handle_caller_frame(pcm16)`` (one 20 ms 8 kHz
    frame of caller audio) and push bot speech in with
    ``_ingest_bot_audio(pcm16, rate)``.
    """

    TAG = "ai"

    def __init__(self, call):
        super().__init__(call)
        self._running = False
        self._playout: deque = deque()     # encoded frames awaiting the pacer
        self._pending = bytearray()        # partial 8 kHz s16 frame from bot
        self._down_state = None            # ratecv state src -> 8k
        self._src_rate = None              # bot audio rate seen so far
        self._lowpass = None
        self._last_bot_frame = 0.0         # monotonic time of last real frame
        # Full-precision G.711: pyVoIP's own encoder squeezes audio through
        # 8-bit linear PCM first, losing 6 bits of G.711's dynamic range —
        # an audible hiss/static floor.  When the pyVoIP internals are
        # available we encode 16-bit -> G.711 ourselves and mark the RTP
        # client to pass our payload through untouched.
        self._encode = None                # 16-bit PCM -> G.711, or None
        self._silence = SILENCE_U8         # one 20 ms silence frame
        # Set by tool actions (end_call / transfer): the controller's tick
        # loop acts on these once the bot's speech has finished playing out
        # and no hold is pending (a barge-in during the goodbye holds the
        # hangup until we know whether it was real speech or line noise).
        self.wants_hangup = False
        self.transfer_target = None
        self._hangup_hold_until = 0.0
        self._referred_at = None
        # Set when the caller talks us out of a transfer that is already
        # dialling; the controller's transfer thread watches this.
        self._transfer_cancelled = False
        # stats for the diagnostic log
        self._n_real = 0
        self._n_fill = 0
        self._n_interrupts = 0
        self._bot_bytes = 0
        # …and the same for the INBOUND path. Without these, "the agent
        # cannot hear me" is indistinguishable from "the caller said
        # nothing": both look like silence in the log. Counting frames and
        # tracking the loudest one separates a dead RTP receive path from a
        # VAD threshold that is set too high.
        self._n_caller_frames = 0
        self._caller_peak_rms = 0
        self._tap_file = None

    # ---------- lifecycle ----------

    def start(self) -> None:
        self._running = True
        self._open_tap()
        self._setup_g711()
        _win_timer_resolution(True)
        threading.Thread(target=self._rx_loop, daemon=True,
                         name=f"{self.TAG}-rx").start()
        threading.Thread(target=self._feeder_loop, daemon=True,
                         name=f"{self.TAG}-tx").start()

    def stop(self) -> None:
        if self._running:
            self._running = False
            _win_timer_resolution(False)
            self._close_tap()

    def _active(self) -> bool:
        return self._running and self.call.state == CallState.ANSWERED

    def _setup_g711(self) -> None:
        try:
            clients = self.call.RTPClients
            pref = clients[0].preference
            if pref == PayloadType.PCMA:
                self._encode = lambda pcm16: audioop.lin2alaw(pcm16, 2)
            elif pref == PayloadType.PCMU:
                self._encode = lambda pcm16: audioop.lin2ulaw(pcm16, 2)
            else:
                diag.log(f"{self.TAG}: unexpected codec {pref}, "
                         "using pyVoIP 8-bit encode")
                return
            for client in clients:
                client.raw_g711 = True
            self._silence = self._encode(SILENCE_16)
            diag.log(
                f"{self.TAG}: full-precision G.711 ({pref}) — "
                f"clients={[(c.inPort, str(c.outIP) + ':' + str(c.outPort)) for c in clients]}"
            )
            if len(clients) > 1:
                diag.log(f"{self.TAG}: WARNING {len(clients)} RTP clients on "
                         "one call — possible SDP multi-connection quirk")
        except Exception as e:
            self._encode = None
            self._silence = SILENCE_U8
            diag.log(f"{self.TAG}: no pyVoIP internals ({e}), "
                     "using pyVoIP 8-bit encode")

    # ---------- caller -> subclass ----------

    def _bot_speaking(self) -> bool:
        return bool(self._playout) or (
            time.monotonic() - self._last_bot_frame < ECHO_GATE_HANGOVER
        )

    def _gate_caller_audio(self, pcm16: bytes) -> bytes:
        """Suppress line echo of the bot's own voice while it is speaking,
        without blocking a genuinely loud interruption from the caller."""
        if self._bot_speaking() and audioop.rms(pcm16, 2) < BARGE_IN_RMS:
            return SILENCE_16
        return pcm16

    def _tap(self, pcm16: bytes) -> None:
        """Write everything the caller sent to a WAV, when VOICE_TAP_INBOUND
        is set. "The agent cannot hear me" has too many possible causes to
        reason about — a codec mismatch, a dead receive path, a VAD
        threshold — and they all look identical in the log. Listening to
        exactly what arrived settles it in one call."""
        if self._tap_file is None:
            return
        try:
            self._tap_file.writeframes(pcm16)
        except Exception:
            pass

    def _open_tap(self) -> None:
        if os.environ.get("VOICE_TAP_INBOUND") not in ("1", "true", "yes"):
            return
        try:
            diag.CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = (diag.CALL_LOG_DIR
                    / f"inbound-{time.strftime('%Y%m%d-%H%M%S')}.wav")
            tap = wave.open(str(path), "wb")
            tap.setnchannels(1)
            tap.setsampwidth(2)
            tap.setframerate(RATE)
            self._tap_file = tap
            diag.log(f"{self.TAG}: tapping inbound audio to {path.name}")
        except Exception as e:
            diag.log(f"{self.TAG}: could not open the inbound tap ({e!r})")

    def _close_tap(self) -> None:
        tap, self._tap_file = self._tap_file, None
        if tap is not None:
            try:
                tap.close()
            except Exception:
                pass

    def _rx_loop(self) -> None:
        while self._active():
            try:
                u8 = self.call.read_audio(FRAMES, blocking=True)
            except Exception:
                break
            if not u8:
                continue
            try:
                pcm16 = u8_to_s16(u8)
                self._tap(pcm16)
                self._n_caller_frames += 1
                rms = audioop.rms(pcm16, 2)
                if rms > self._caller_peak_rms:
                    self._caller_peak_rms = rms
                self._handle_caller_frame(pcm16)
            except Exception as e:
                diag.log(f"{self.TAG}: caller frame handler failed: {e!r}")

    def _handle_caller_frame(self, pcm16: bytes) -> None:
        raise NotImplementedError

    # ---------- bot -> caller: keep pyVoIP's TX buffer topped up ----------

    def _backlog_frames(self):
        """How many 20 ms frames are queued in pyVoIP's outgoing RTP buffer,
        i.e. written by us but not yet transmitted.  None if the pyVoIP
        internals aren't available (e.g. a stub call in tests)."""
        try:
            rtp = self.call.RTPClients[0]
            pm = rtp.pmout
            with pm.bufferLock:
                read_abs = pm.offset + pm.buffer.tell()
            n = (rtp.outOffset - read_abs) / FRAMES
            # Before the first write pm.offset is a 2**32 sentinel.
            return max(0.0, n) if n > -1000 else 0.0
        except Exception:
            return None

    def _feeder_loop(self) -> None:
        last_stats = time.monotonic()
        while self._active():
            now = time.monotonic()
            if now - last_stats >= 5.0:
                last_stats = now
                tx_threads = sum(
                    1 for t in threading.enumerate()
                    if t.name == "RTP Transmitter"
                )
                diag.log(
                    f"stats: playout={len(self._playout)} "
                    f"backlog={self._backlog_frames()} "
                    f"frames real/fill={self._n_real}/{self._n_fill} "
                    f"{self.TAG}_rx={self._bot_bytes}B "
                    f"caller_frames={self._n_caller_frames} "
                    f"caller_peak_rms={self._caller_peak_rms} "
                    f"interrupts={self._n_interrupts} "
                    f"rtp_tx_threads={tx_threads}"
                )
                if self._n_caller_frames == 0:
                    diag.log("stats: WARNING no caller audio received at "
                             "all — the RTP receive path is dead, not the "
                             "caller")
                if tx_threads > 1:
                    diag.log("stats: WARNING multiple RTP transmit threads — "
                             "duplicate-transmitter bug is back")
            backlog = self._backlog_frames()
            try:
                if backlog is None:
                    # No pyVoIP internals: plain 20 ms open-loop pacing.
                    self.call.write_audio(self._next_frame())
                    time.sleep(FRAMES / RATE)
                    continue
                wrote = 0
                while backlog + wrote < CUSHION_FRAMES and wrote < 12:
                    self.call.write_audio(self._next_frame())
                    wrote += 1
            except Exception:
                break
            time.sleep(0.005)

    def _next_frame(self) -> bytes:
        if self._playout:
            self._last_bot_frame = time.monotonic()
            self._n_real += 1
            return self._playout.popleft()
        self._n_fill += 1
        return self._silence

    def _ingest_bot_audio(self, pcm16: bytes, rate: int) -> None:
        """Queue bot speech (16-bit mono PCM at ``rate``) for playout."""
        self._bot_bytes += len(pcm16)
        if rate != self._src_rate:
            self._src_rate = rate
            self._down_state = None
            self._lowpass = _AntiAliasFilter(rate)
        pcm16 = audioop.mul(pcm16, 2, OUTPUT_GAIN)
        if rate == RATE:
            down = pcm16
        else:
            down, self._down_state = audioop.ratecv(
                self._lowpass.process(pcm16), 2, 1, rate, RATE,
                self._down_state
            )
        self._pending += down
        step = FRAMES * 2
        while len(self._pending) >= step:
            frame16 = bytes(self._pending[:step])
            del self._pending[:step]
            self._playout.append(
                self._encode(frame16) if self._encode else s16_to_u8(frame16)
            )

    def _flush_playout(self) -> None:
        self._playout.clear()
        self._pending.clear()
