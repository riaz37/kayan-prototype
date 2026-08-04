"""
Agent configuration. Every value can be overridden by an environment variable
of the same name (or a .env file next to the project root).
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- WhatsApp (Meta Cloud API)
    whatsapp_verify_token: str = "kayan-verify-token"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""

    backend_url: str = "http://localhost:8001"
    port: int = 8002

    # ---- LLM
    # Any OpenAI-compatible endpoint. Set LLM_BASE_URL / LLM_MODEL in .env —
    # the default here is a local vLLM so that no real endpoint is hardcoded in
    # a public repository. Previously this pointed at OpenRouter's free tier,
    # which meant the provider had to be swapped by hand whenever a key ran out
    # (git history shows five such swaps).
    llm_base_url: str = "http://localhost:8000"
    llm_api_key: str = "none"
    llm_model: str = "qwen"
    llm_fallback_model: str = ""

    # This model returns its chain of thought in a separate `reasoning` field.
    # Thinking costs latency that a WhatsApp reply cannot afford, so it is off
    # by default; flip llm_enable_thinking=1 to debug the agent's decisions.
    llm_enable_thinking: bool = False
    llm_temperature: float = 0.3
    llm_top_p: float = 0.95
    llm_top_k: int = 20
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 60.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
