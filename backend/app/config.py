from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, urlparse

from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./llm_router.db"
    database_drivername: str = ""
    database_host: str = ""
    database_port: int | None = None
    database_name: str = ""
    database_user: str = ""
    database_password: str = ""
    database_query: str = ""
    auto_create_schema: bool = True
    run_migrations_on_startup: bool = False

    # Developer DB tooling
    dev_db_tools_enabled: bool = False
    dev_db_tools_require_localhost: bool = True

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
    def resolved_database_url(self) -> str:
        # If component-based config is provided, build URL safely so
        # special chars (e.g. '#') in password are encoded correctly.
        if self.database_host and self.database_name and self.database_user and self.database_password:
            drivername = self.database_drivername or "mssql+aioodbc"
            query_dict = dict(parse_qsl(self.database_query, keep_blank_values=True))
            if drivername.startswith("mssql"):
                return self._build_mssql_aioodbc_url(query_dict)
            return str(
                URL.create(
                    drivername=drivername,
                    username=self.database_user,
                    password=self.database_password,
                    host=self.database_host,
                    port=self.database_port,
                    database=self.database_name,
                    query=query_dict,
                )
            )
        return self.database_url

    def _build_mssql_aioodbc_url(self, query_dict: dict[str, str]) -> str:
        driver = query_dict.pop("driver", "ODBC Driver 18 for SQL Server")
        encrypt = query_dict.pop("Encrypt", "yes")
        trust_cert = query_dict.pop("TrustServerCertificate", "no")
        timeout = query_dict.pop("Connection Timeout", "30")
        port = self.database_port or 1433

        escaped_password = self.database_password.replace("}", "}}")
        parts = [
            f"Driver={{{driver}}}",
            f"Server=tcp:{self.database_host},{port}",
            f"Database={self.database_name}",
            f"Uid={self.database_user}",
            f"Pwd={{{escaped_password}}}",
            f"Encrypt={encrypt}",
            f"TrustServerCertificate={trust_cert}",
            f"Connection Timeout={timeout}",
        ]
        for key, value in query_dict.items():
            parts.append(f"{key}={value}")
        odbc_connect = ";".join(parts) + ";"
        return f"mssql+aioodbc:///?odbc_connect={quote_plus(odbc_connect)}"

    @property
    def database_scheme(self) -> str:
        return urlparse(self.resolved_database_url).scheme

    @property
    def is_sqlite_database(self) -> bool:
        return self.database_scheme.startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173"]

    model_config = {"env_file": _BACKEND_DIR / ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
