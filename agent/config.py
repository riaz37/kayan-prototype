from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_verify_token: str = "kayan-verify-token"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    backend_url: str = "http://localhost:8001"
    port: int = 8002

    llm_api_key: str = ""
    llm_base_url: str = "https://reviewer-mac-cartridge-closer.trycloudflare.com"
    llm_model: str = "qwen"
    llm_fallback_model: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
