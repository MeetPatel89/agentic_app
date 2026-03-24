from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SQLDialect(StrEnum):
    postgresql = "postgresql"
    tsql = "tsql"
    mysql = "mysql"
    sqlite = "sqlite"
    bigquery = "bigquery"
    snowflake = "snowflake"


class NL2SQLRequest(BaseModel):
    provider: str
    model: str
    natural_language: str = Field(..., min_length=1, description="Natural language query to convert to SQL")
    dialect: SQLDialect = SQLDialect.postgresql
    system_prompt: str | None = Field(
        None,
        description="Large context blob containing schema definitions, business rules, and few-shot examples",
    )
    temperature: float | None = 0.7
    max_tokens: int = 2048
    sandbox_ddl: str | None = Field(
        None,
        description="DDL statements for creating in-memory sandbox tables (CREATE TABLE ...)",
    )
    provider_options: dict[str, Any] = Field(default_factory=dict)


class SQLValidationResult(BaseModel):
    is_valid: bool
    syntax_errors: list[str] = Field(default_factory=list)
    transpiled_sql: str | None = None
    sandbox_execution_success: bool | None = None
    sandbox_error: str | None = None


class NL2SQLResponse(BaseModel):
    generated_sql: str
    explanation: str
    dialect: SQLDialect
    validation: SQLValidationResult
    usage: dict[str, int | None] = Field(default_factory=dict)
    run_id: str | None = None
    latency_ms: float | None = None


class SQLValidateRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    dialect: SQLDialect = SQLDialect.postgresql
    sandbox_ddl: str | None = None


class SQLExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    dialect: SQLDialect = SQLDialect.postgresql
    connection_string: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_rows: int = Field(default=1000, ge=1, le=50000)


class SQLExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool = False


class NL2SQLStreamFinal(BaseModel):
    type: str = "final"
    generated_sql: str
    explanation: str
    dialect: SQLDialect
    validation: SQLValidationResult
    usage: dict[str, int | None] = Field(default_factory=dict)
    run_id: str | None = None
    latency_ms: float | None = None
