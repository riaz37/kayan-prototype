"""Shared audio primitives: PCM conversions and framing.

pyVoIP exchanges call audio as 8-bit unsigned linear PCM at 8000 Hz in
160-byte (20 ms) chunks.  Everything else here works in signed 16-bit and
converts at the boundary with audioop.

Ported from esap-voice `app/audio.py`.  The tone generator and TonePlayer
went with it: they drove a local sound card so a human could hear a ringer
on a desktop softphone.  This engine auto-answers on a server with no
sound card, so keeping them would only have added a `sounddevice`
dependency that fails to import in a container.
"""
import audioop

RATE = 8000
FRAMES = 160  # 20 ms per chunk
SILENCE_16 = b"\x00" * (FRAMES * 2)
SILENCE_U8 = b"\x80" * FRAMES


def u8_to_s16(data: bytes) -> bytes:
    """pyVoIP call audio (8-bit unsigned) -> signed 16-bit PCM."""
    return audioop.lin2lin(audioop.bias(data, 1, -128), 1, 2)


def s16_to_u8(data: bytes) -> bytes:
    """Signed 16-bit PCM -> pyVoIP call audio (8-bit unsigned)."""
    return audioop.bias(audioop.lin2lin(data, 2, 1), 1, 128)


def chunks16(pcm16: bytes):
    """Split 16-bit PCM into whole 20 ms frames."""
    step = FRAMES * 2
    for i in range(0, len(pcm16) - step + 1, step):
        yield pcm16[i:i + step]
