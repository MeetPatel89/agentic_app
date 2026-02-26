from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./llm_router.db"

    # CORS
    cors_origins: str = '["http://localhost:5173"]'

    # Logging
    log_level: str = "INFO"

    # Provider keys (all optional – adapter auto-disables when missing)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    groq_api_key: str = ""
    together_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-06-01"

    # Local / OpenAI-compatible
    local_openai_base_url: str = "http://localhost:11434/v1"
    local_openai_api_key: str = "not-needed"

    @property
    def cors_origin_list(self) -> list[str]:
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
