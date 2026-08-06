"""Speech in and out, shared by every transport.

The phone (RTP at 8 kHz) and the browser (WebSocket at 16 kHz) move audio
very differently, but the calls to the STT and TTS servers must stay
identical — including the transcript cleaning that took several live
calls to get right.  Both live here so there is one implementation.

Ported from esap-voice `app/speech.py`.  Added here: `tts_config_for`,
which picks the synthesizer's language per utterance instead of pinning it
in config (see its docstring).
"""
import audioop
import io
import re
import wave

from . import diag
from . import digits

STT_RATE = 16000          # Whisper-family models prefer 16 kHz input
RAW_TTS_RATE = 24000      # assumed rate when TTS returns headerless PCM

# Callers speak English or Arabic; other scripts in a transcript are the
# ASR's language detection guessing, but a whole utterance in one script
# is usually a real transcription in the wrong alphabet (a caller's name)
# and must NOT be dropped — see _clean_transcript.
_EXPECTED_CHARS = re.compile(r"[A-Za-z؀-ۿ]")
_FOREIGN_CHARS = re.compile(r"[Ͱ-׿ऀ-῿⺀-퟿豈-﫿]")


def clean_transcript(text: str) -> str:
    """Strip inline ASR markup (nemotron tags the detected locale), trim
    stray hallucinated characters, and turn spoken digit runs into digits.

    A caller reads their number out as words; the model then stores the
    words and the team gets a lead nobody can ring. Rewriting the run here
    means every channel that uses STT sees a real number.
    """
    text = re.sub(r"\s*<[a-zA-Z][a-zA-Z0-9_-]*>\s*", " ", text or "").strip()
    spoken = digits.spoken_to_digits(text)
    if spoken != text:
        diag.log(f"speech: spoken digits -> {spoken[:80]!r}")
        text = spoken
    foreign = len(_FOREIGN_CHARS.findall(text))
    if not foreign:
        return text
    expected = len(_EXPECTED_CHARS.findall(text))
    if foreign > expected:
        diag.log(f"speech: transcript in foreign script, passing "
                 f"through: {text[:80]!r}")
        return text
    return _FOREIGN_CHARS.sub("", text).strip()


# Real turns that are genuinely this short. Anything else of one or two
# letters is echo or noise that the recogniser felt obliged to name.
_REAL_SHORT_TURNS = {
    "no", "ok", "hi", "yes", "yep", "nah", "bye",
    "لا", "اي", "أي", "نعم", "ايه", "إيه", "طيب", "هلا", "ايوه", "أيوه",
}


def is_meaningful_turn(text: str) -> bool:
    """Did the caller actually say something, or did STT name a noise?

    Speech recognition never answers "I heard nothing" — handed a fragment
    of the agent's own voice leaking back from a speaker, it returns the
    closest word. A live browser session transcribed "Lo" and "I" out of
    the agent's own reply and answered both as if they were questions.

    An utterance with one or two letters in it and no digits is not a turn.
    The handful of real words that short are listed above; a phone number
    fragment ("07") is a turn, and is handled by the number holding.
    """
    stripped = (text or "").strip()
    if not stripped:
        return False
    if any(c.isdigit() for c in stripped):
        return True
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) > 2:
        return True
    return "".join(letters).lower() in _REAL_SHORT_TURNS


def parse_tts_audio(data: bytes):
    """(mono s16 PCM, rate) from a TTS response: a PCM WAV when the server
    honoured ``response_format="wav"``, else assumed raw 24 kHz."""
    if data[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(data)) as w:
                rate = w.getframerate()
                width = w.getsampwidth()
                channels = w.getnchannels()
                pcm = w.readframes(w.getnframes())
            if width == 1:                      # 8-bit WAV is unsigned
                pcm = audioop.lin2lin(audioop.bias(pcm, 1, -128), 1, 2)
            elif width != 2:
                pcm = audioop.lin2lin(pcm, width, 2)
            if channels == 2:
                pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
            return pcm, rate
        except Exception as e:
            diag.log(f"speech: WAV parse failed ({e!r}), treating as raw")
    return data, RAW_TTS_RATE


def make_client(cfg: dict, timeout: float = 30.0):
    from openai import OpenAI
    import os
    return OpenAI(
        base_url=(cfg or {}).get("base_url") or None,
        # Local OpenAI-compatible servers usually accept any key.
        api_key=((cfg or {}).get("api_key")
                 or os.environ.get("OPENAI_API_KEY") or "not-needed"),
        timeout=timeout,
        max_retries=1,
    )


def transcribe(client, stt: dict, pcm: bytes, rate: int) -> str:
    """One utterance of 16-bit mono PCM at ``rate`` -> cleaned text."""
    if rate != STT_RATE:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, STT_RATE, None)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(STT_RATE)
        w.writeframes(pcm)
    # Provider params, e.g. language pinning ({"language": "ar"} for
    # servers that hallucinate on a wrong default language).
    kw = dict((stt or {}).get("params") or {})
    kw.update(model=(stt or {}).get("model", ""),
              file=("utterance.wav", buf.getvalue(), "audio/wav"))
    resp = client.audio.transcriptions.create(**kw)
    return clean_transcript(getattr(resp, "text", "") or "")


def synthesize(client, tts: dict, text: str):
    """One chunk of speech; returns (mono s16 PCM, rate)."""
    kw = {"response_format": "wav"}
    kw.update((tts or {}).get("params") or {})
    kw.update(model=(tts or {}).get("model", ""),
              voice=(tts or {}).get("voice", "") or "alloy",
              input=text)
    resp = client.audio.speech.create(**kw)
    return parse_tts_audio(resp.read())


# Arabic script, including the presentation forms an ASR sometimes emits.
_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﻿]")
_LATIN = re.compile(r"[A-Za-z]")


def is_arabic(text: str) -> bool:
    """Is this sentence more Arabic than Latin?"""
    return len(_ARABIC.findall(text or "")) >= len(_LATIN.findall(text or ""))


def tts_config_for(text: str, base: dict) -> dict:
    """The TTS config for one utterance, with its language filled in.

    OmniVoice takes `language` in extra_body. Pinning it to Arabic ("ars")
    in configuration is wrong for a bilingual service: the agent mirrors
    the caller's language, and an English sentence synthesized as Arabic
    comes out as mush. Choosing per utterance costs nothing — the config is
    rebuilt per chunk anyway — and keeps the same cloned voice for both.
    """
    cfg = dict(base or {})
    params = dict(cfg.get("params") or {})
    extra = dict(params.get("extra_body") or {})
    extra["language"] = "ars" if is_arabic(text) else "eng"
    params["extra_body"] = extra
    cfg["params"] = params
    return cfg
