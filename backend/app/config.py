"""Settings loaded from environment variables / backend/.env"""
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Put .env values into os.environ too, so optional tools (LangSmith tracing) see them.
load_dotenv(ENV_FILE)

EMBEDDING_DIM = 1536  # text-embedding-3-small. Must match vector(1536) in sql/schema.sql

SUPPORTED_LANGUAGES = [
    "auto", "English", "Hindi", "Bengali", "Marathi",
    "Telugu", "Tamil", "Gujarati", "Kannada", "Malayalam",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore", case_sensitive=False)

    # Required
    openai_api_key: str
    database_url: str
    supabase_url: str
    supabase_anon_key: str

    # Models
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # "0" works for gpt-4o-mini. Reasoning models (gpt-5 family) reject it: set to "default".
    openai_temperature: str = "0"
    openai_reasoning_effort: str = ""  # optional, e.g. "low" for reasoning models

    # Web
    frontend_origins: str = "http://localhost:3000"
    cors_origin_regex: str = ""

    # Behaviour
    retrieval_k: int = 8
    max_retrieval_retries: int = 1
    max_regenerations: int = 1
    history_messages: int = 6
    max_message_chars: int = 1500
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 600

    @field_validator("supabase_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @field_validator("openai_api_key", "database_url", "supabase_anon_key")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
