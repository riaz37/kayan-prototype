"""Runtime patches for pyVoIP 1.6.8's RTP layer.

Patch 1 — drift-free transmit pacing.  Stock pyVoIP paces its transmit
thread with relative sleeps (``sleep(0.02 - elapsed)``), so packet spacing
jitters and drifts.  Endpoints with adaptive jitter buffers (e.g.
Grandstream) absorb that; strict, small-buffer media paths (old Avaya
phones, IP Office DSP/trunk legs) repeatedly under/overrun and the audio
screeches.  The replacement keeps the identical packet format but sends on
an absolute 20 ms schedule from ``time.monotonic`` so error never
accumulates.  It also fixes two stock bugs: on sequence-number overflow
pyVoIP emitted a malformed packet with no sequence field (breaks calls at
~22 min), and the 32-bit timestamp overflowed the same way — both now wrap
as RFC 3550 requires.

Patch 2 — safe mid-call re-INVITE handling.  Stock ``renegotiate`` calls
``gen_ms()``, which calls ``start()`` on RTP clients that are ALREADY
RUNNING (pyVoIP's own TODO calls this "dangerous"): the socket is rebound
and a second receive + transmit thread pair spawns on the same client.
Two transmit threads share one outgoing buffer and one sequence counter,
so they split the audio between them at double drain rate with interleaved
corrupt sequence numbers — garbled, screeching audio.  Avaya IP Office
sends exactly such re-INVITEs ("media shuffling") on calls involving older
phones or external trunks, which is why those screeched while direct
SIP-to-SIP calls sounded fine.  The replacement re-answers with the
ports/codecs already in use and just repoints the RTP destination.
"""
import time

from pyVoIP import RTP
from pyVoIP.VoIP import VoIPCall

from .. import diag


def _paced_trans(self) -> None:
    frame_period = 160 / self.preference.rate  # 0.02 s for 8 kHz G.711
    next_send = time.monotonic()
    while self.NSD:
        payload = self.pmout.read()
        # A transport may write pre-encoded G.711 (full 16-bit precision
        # instead of pyVoIP's lossy 8-bit intermediate); pass it through.
        if not getattr(self, "raw_g711", False):
            payload = self.encode_packet(payload)
        packet = b"\x80"  # RFC 1889 V2, no padding/extension/CC
        packet += chr(int(self.preference)).encode("utf8")
        packet += (self.outSequence & 0xFFFF).to_bytes(2, byteorder="big")
        packet += (self.outTimestamp & 0xFFFFFFFF).to_bytes(
            4, byteorder="big"
        )
        packet += self.outSSRC.to_bytes(4, byteorder="big")
        packet += payload

        try:
            self.sout.sendto(packet, (self.outIP, self.outPort))
        except OSError:
            pass

        self.outSequence = (self.outSequence + 1) & 0xFFFF
        self.outTimestamp = (self.outTimestamp + len(payload)) & 0xFFFFFFFF

        next_send += frame_period
        delay = next_send - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif delay < -0.2:
            # A long stall (GC, scheduler); resync instead of burst-sending
            # 10+ packets that a strict jitter buffer would drop anyway.
            next_send = time.monotonic()


def _safe_renegotiate(self, request) -> None:
    m = {client.inPort: client.assoc for client in self.RTPClients}
    message = self.sip.gen_answer(request, self.session_id, m, self.sendmode)
    self.sip.out.sendto(
        message.encode("utf8"), (self.phone.server, self.phone.port)
    )
    for i in request.body["m"]:
        if i["type"] == "video":
            continue
        for ii, client in zip(
            range(len(request.body["c"])), self.RTPClients
        ):
            client.outIP = request.body["c"][ii]["address"]
            client.outPort = i["port"] + ii
            diag.log(
                f"re-INVITE: media repointed to "
                f"{client.outIP}:{client.outPort} "
                f"(m-line type={i['type']} methods={i.get('methods')})"
            )


def _raw_parse(original):
    """Keep the G.711 payload undecoded when the client is in passthrough
    mode (call bridging), so audio crosses two legs bit-exact instead of
    going through pyVoIP's lossy 8-bit linear intermediate."""
    def parse(self, packet):
        if getattr(self, "raw_g711_in", False):
            # One G.711 byte per sample: same length as the decoded form,
            # so the jitter buffer behaves identically.
            self.pmin.write(packet.timestamp, packet.payload)
            return
        return original(self, packet)
    return parse


def apply_rtp_timing_patch() -> None:
    RTP.RTPClient.trans = _paced_trans
    RTP.RTPClient.parse_pcmu = _raw_parse(RTP.RTPClient.parse_pcmu)
    RTP.RTPClient.parse_pcma = _raw_parse(RTP.RTPClient.parse_pcma)
    VoIPCall.renegotiate = _safe_renegotiate
