from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_verify_token: str = "kayan-verify-token"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    backend_url: str = "http://localhost:8001"
    port: int = 8002

    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api"
    llm_model: str = "qwen/qwen-2.5-72b-instruct"
    llm_fallback_model: str = ""

    embedding_base_url: str = "https://embedd.arahim.dev"
    embedding_model: str = "qwen3-embedding-0.6b"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
