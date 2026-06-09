from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "dev")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")

    api_key: str = os.getenv("API_KEY", "")
    base_url: str = os.getenv("BASE_URL", "")

settings = Settings()