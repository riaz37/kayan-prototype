"""Media-level call transfer: bridge two SIP legs inside the engine.

Avaya IP Office answers a blind REFER from a third-party SIP extension
with "405 Method Not Allowed" — Avaya only supports consultative transfer
for SIP endpoints, and documents blind transfer as unsupported.  So when
REFER is refused we transfer the call ourselves: place a second call to
the target extension and, once it answers, relay RTP payloads between the
two legs.  The line stays in the middle (it keeps one channel busy) but
the caller reaches a human on any PBX, with no PBX cooperation at all.

Audio is forwarded as raw G.711 whenever both legs agreed on the same
codec, so the bridged audio is bit-exact — no decode/re-encode through
pyVoIP's lossy 8-bit intermediate.
"""
import threading
import time

from pyVoIP.VoIP import CallState

from . import diag

FRAME = 160          # 20 ms of G.711 at 8 kHz
IDLE_SLEEP = 0.002


def _codecs_match(a, b) -> bool:
    try:
        return (a.RTPClients[0].preference == b.RTPClients[0].preference)
    except Exception:
        return False


def _set_passthrough(call, enabled: bool) -> None:
    """Ask our RTP patches to skip decode on read and encode on write."""
    for client in getattr(call, "RTPClients", []):
        client.raw_g711 = enabled
        client.raw_g711_in = enabled


class CallBridge:
    """Relays audio between two answered calls until either one ends."""

    def __init__(self, a, b):
        self.a = a
        self.b = b
        self._running = False
        self._threads = []
        self.passthrough = False

    def start(self) -> None:
        self.passthrough = _codecs_match(self.a, self.b)
        if self.passthrough:
            _set_passthrough(self.a, True)
            _set_passthrough(self.b, True)
        else:
            diag.log("bridge: codecs differ — relaying through pyVoIP's "
                     "8-bit path")
        self._running = True
        for src, dst, name in ((self.a, self.b, "a2b"),
                               (self.b, self.a, "b2a")):
            t = threading.Thread(target=self._pump, args=(src, dst),
                                 daemon=True, name=f"bridge-{name}")
            t.start()
            self._threads.append(t)
        diag.log(f"bridge: relaying audio (passthrough="
                 f"{'on' if self.passthrough else 'off'})")

    def alive(self) -> bool:
        return (self._running
                and self.a.state == CallState.ANSWERED
                and self.b.state == CallState.ANSWERED)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        # Leave the write path as pyVoIP expects it for any later teardown.
        for call in (self.a, self.b):
            try:
                _set_passthrough(call, False)
            except Exception:
                pass
        diag.log("bridge: stopped")

    def _pump(self, src, dst) -> None:
        while self.alive():
            try:
                data = src.read_audio(FRAME, blocking=True)
            except Exception:
                break
            if not data:
                time.sleep(IDLE_SLEEP)
                continue
            try:
                dst.write_audio(data)
            except Exception:
                break
        self._running = False
