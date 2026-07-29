from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_verify_token: str = "kayan-verify-token"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    backend_url: str = "http://localhost:8000"
    port: int = 8001

    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "gemini-2.0-flash"
    llm_fallback_model: str = "gemini-2.0-flash-lite"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
