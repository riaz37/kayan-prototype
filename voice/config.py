"""Voice engine configuration.

Same pattern as agent/config.py: every value is overridable by an
environment variable of the same name, read from `.env` at the project
root.

STT and TTS point at a self-hosted Arabic speech stack. No reachable
endpoint is defaulted here — this repository is public, so the real hosts
come from STT_BASE_URL / TTS_BASE_URL in `.env`, which is gitignored (same
reasoning as agent/config.py and the LLM endpoint). The defaults below are
localhost, so a fresh clone starts and fails to reach speech rather than
reaching someone else's machine.

Both are currently tailnet-only, which is why the engine has to run
somewhere that can see them. When they get proxied, only these two base
URLs change.
"""
from pydantic_settings import BaseSettings


class VoiceSettings(BaseSettings):
    # ---- where the rest of Kayan lives
    backend_url: str = "http://127.0.0.1:8001"
    agent_url: str = "http://127.0.0.1:8002"
    # 8001 backend, 8002 agent, 8003 baileys bridge, 3000 console.
    voice_port: int = 8004

    # ---- SIP line
    # Blank sip_server means "don't register" — the engine still starts and
    # serves the browser-mic path, which is how it runs with no PBX around.
    sip_server: str = ""
    sip_port: int = 5060
    sip_username: str = ""
    sip_password: str = ""
    # Our own UDP port. pyVoIP binds this; each line needs its own.
    sip_local_port: int = 15060
    sip_auto_answer: bool = True
    # Extension a call is handed to when the agent calls transfer_to_human.
    sip_transfer_target: str = "1002"
    sip_line_label: str = "kayan-voice"

    # ---- STT: nemotron streaming ASR (:9027)
    # language "auto" on purpose. This model obeys `language` literally —
    # forcing "ar" on English audio returns an empty string — and Kayan's
    # callers mix Arabic and English. Its detection handles both.
    stt_base_url: str = "http://127.0.0.1:9027/v1"
    stt_api_key: str = "none"
    stt_model: str = "nemotron-asr"
    stt_language: str = "auto"

    # ---- TTS: OmniVoice (:9020)
    # `language` is NOT set here — it is chosen per utterance from the
    # script of the text (see voice.speech.tts_config_for), because pinning
    # "ars" makes an English sentence come out mangled.
    tts_base_url: str = "http://127.0.0.1:9020/v1"
    tts_api_key: str = "none"
    tts_model: str = "k2-fsa/OmniVoice"
    tts_voice: str = "ar_female_warm.wav"
    # Quality/latency knob for OmniVoice. 16 is what esap-voice settled on
    # for a phone call.
    tts_num_step: int = 16

    # ---- turn taking
    # Seconds of silence that end a caller's utterance. Every reply starts
    # this long after they stop talking, so it is pure added latency; below
    # ~0.4s, mid-sentence pauses get chopped into two turns.
    end_silence_seconds: float = 0.5
    # How long the engine waits for the agent to answer one turn.
    # A turn that calls a tool is two LLM rounds; measured at ~9s each
    # once the prompt passes ~5k tokens. 25s cut those off mid-answer.
    agent_timeout_seconds: float = 45.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8",
                    "extra": "ignore"}

    # ---- derived views, in the shape voice/speech.py wants

    def stt_config(self) -> dict:
        return {
            "base_url": self.stt_base_url,
            "api_key": self.stt_api_key,
            "model": self.stt_model,
            "params": {"language": self.stt_language},
        }

    def tts_config(self) -> dict:
        return {
            "base_url": self.tts_base_url,
            "api_key": self.tts_api_key,
            "model": self.tts_model,
            "voice": self.tts_voice,
            "params": {"extra_body": {"num_step": self.tts_num_step}},
        }


settings = VoiceSettings()
