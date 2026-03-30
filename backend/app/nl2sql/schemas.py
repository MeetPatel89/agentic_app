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


class NL2SQLHistoryMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


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
    conversation_history: list[NL2SQLHistoryMessage] = Field(
        default_factory=list,
        description="Prior user/assistant turns for multi-turn SQL refinement",
    )
    provider_options: dict[str, Any] = Field(default_factory=dict)


class SQLQuery(BaseModel):
    title: str = Field(..., description="Short descriptive title for this query approach")
    sql: str = Field(..., description="The SQL query")
    explanation: str = Field("", description="Explanation of the approach, tradeoffs, or caveats")


class SQLValidationResult(BaseModel):
    is_valid: bool
    syntax_errors: list[str] = Field(default_factory=list)
    transpiled_sql: str | None = None
    sandbox_execution_success: bool | None = None
    sandbox_error: str | None = None


class NL2SQLResponse(BaseModel):
    generated_sql: str = Field(..., description="SQL from the recommended query (backward compat)")
    explanation: str = Field("", description="Explanation from the recommended query (backward compat)")
    queries: list[SQLQuery] = Field(default_factory=list, description="All generated query variants")
    recommended_index: int = Field(0, description="Index into queries for the recommended approach")
    assumptions: list[str] = Field(default_factory=list, description="Assumptions the LLM made about schema or data")
    dialect: SQLDialect
    validation: SQLValidationResult
    usage: dict[str, int | None] = Field(default_factory=dict)
    run_id: str | None = None
    latency_ms: float | None = None
    raw_llm_output: str = Field(
        "",
        description="Verbatim model completion text (JSON or prose) before structured parsing",
    )


class SQLValidateRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    dialect: SQLDialect = SQLDialect.postgresql
    sandbox_ddl: str | None = None


class SQLExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    dialect: SQLDialect = SQLDialect.postgresql
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_rows: int = Field(default=1000, ge=1, le=50000)
    read_only: bool = True


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
    queries: list[SQLQuery] = Field(default_factory=list)
    recommended_index: int = 0
    assumptions: list[str] = Field(default_factory=list)
    dialect: SQLDialect
    validation: SQLValidationResult
    usage: dict[str, int | None] = Field(default_factory=dict)
    run_id: str | None = None
    latency_ms: float | None = None
    raw_llm_output: str = ""
