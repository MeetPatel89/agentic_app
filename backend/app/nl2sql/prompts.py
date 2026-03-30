from __future__ import annotations

from typing import Any

from app.nl2sql.schemas import SQLDialect

_DIALECT_GUIDANCE: dict[SQLDialect, str] = {
    SQLDialect.postgresql: (
        "Generate PostgreSQL-compatible SQL. Use double quotes for identifiers if needed. "
        "Prefer standard ANSI SQL where possible. Use PostgreSQL-specific features like "
        "ILIKE, generate_series, array types, or CTEs when appropriate."
    ),
    SQLDialect.tsql: (
        "Generate T-SQL (Microsoft SQL Server) compatible SQL. Use square brackets for "
        "identifiers if needed. Use TOP instead of LIMIT. Use GETDATE() instead of NOW(). "
        "Use ISNULL() instead of COALESCE where appropriate. Prefix temp tables with #."
    ),
    SQLDialect.mysql: (
        "Generate MySQL-compatible SQL. Use backticks for identifiers if needed. "
        "Use LIMIT for row limiting. Use IFNULL() or COALESCE(). "
        "Prefer MySQL date functions like DATE_FORMAT, STR_TO_DATE."
    ),
    SQLDialect.sqlite: (
        "Generate SQLite-compatible SQL. SQLite has limited type system — use TEXT, "
        "INTEGER, REAL, BLOB. No ALTER COLUMN support. Use || for string concatenation. "
        "Date functions: date(), time(), datetime(), strftime()."
    ),
    SQLDialect.bigquery: (
        "Generate Google BigQuery Standard SQL. Use backticks for project.dataset.table "
        "references. Use STRUCT and ARRAY types where appropriate. Use SAFE_ prefixed "
        "functions for null-safe operations."
    ),
    SQLDialect.snowflake: (
        "Generate Snowflake SQL. Use double quotes for case-sensitive identifiers. "
        "Leverage Snowflake features like FLATTEN for semi-structured data, "
        "QUALIFY for window function filtering, and TRY_ prefixed functions."
    ),
}

DEFAULT_TEMPLATE = """\
You are an expert SQL engineer. Your task is to convert natural language questions \
into precise, production-quality SQL queries.

## Database Schema
{schema_context}

## SQL Dialect
{dialect_guidance}

## Instructions
- Generate one or more SQL query approaches for the given question.
- When the question has multiple valid interpretations or approaches (e.g., with/without \
handling ties, different performance tradeoffs, strict vs. lenient matching), provide each \
as a separate query.
- For straightforward questions with one clear answer, a single query is fine.
- Set `recommended_index` to the 0-based index of the query you recommend most.
- List any assumptions you made about the schema or data in `assumptions`.

## SQL Rules
- Use meaningful table aliases.
- Prefer explicit JOINs over implicit comma-joins.
- Always qualify column names with table aliases when the query involves multiple tables.
- Use parameterized-style placeholders ($1, :param, or ?) only if the question implies user input.
- Avoid SELECT * in production queries — select only needed columns.
- Use CTEs (WITH clauses) for complex multi-step queries for readability.
- Add appropriate WHERE clauses for safety on UPDATE/DELETE statements.

## Response Format
You MUST respond with a JSON object and nothing else. No markdown fences, no commentary \
outside the JSON. The JSON must match this exact structure:

{{
  "queries": [
    {{
      "title": "Short descriptive title for this approach",
      "sql": "The SQL query text",
      "explanation": "Brief explanation of what this query does and any tradeoffs"
    }}
  ],
  "recommended_index": 0,
  "assumptions": ["Any assumptions made about the schema, data, or ambiguous terms"]
}}

Rules for the JSON response:
- `queries` must contain at least one entry.
- Each `sql` value must be a single, complete SQL statement.
- `recommended_index` must be a valid index into the `queries` array.
- `assumptions` may be an empty array if no assumptions were needed.
"""

# JSON Schema used with OpenAI-family response_format for guaranteed structure.
NL2SQL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "sql": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["title", "sql", "explanation"],
                "additionalProperties": False,
            },
        },
        "recommended_index": {"type": "integer"},
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["queries", "recommended_index", "assumptions"],
    "additionalProperties": False,
}

# Providers whose SDKs accept the OpenAI-style response_format parameter.
RESPONSE_FORMAT_PROVIDERS = frozenset({"openai", "local_openai_compatible", "azure_openai"})


def build_system_prompt(
    *,
    dialect: SQLDialect,
    schema_context: str | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Build the final system prompt for NL-to-SQL generation.

    If custom_prompt is provided, it is used as-is (the developer owns the full prompt).
    Otherwise, the default template is populated with schema_context and dialect guidance.
    """
    if custom_prompt:
        dialect_note = _DIALECT_GUIDANCE.get(dialect, "")
        if dialect_note and "{dialect_guidance}" in custom_prompt:
            return custom_prompt.replace("{dialect_guidance}", dialect_note)
        if "{dialect_guidance}" not in custom_prompt and dialect_note:
            return f"{custom_prompt}\n\n## SQL Dialect\n{dialect_note}"
        return custom_prompt

    return DEFAULT_TEMPLATE.format(
        schema_context=schema_context or "(No schema provided — generate best-effort SQL based on the question.)",
        dialect_guidance=_DIALECT_GUIDANCE.get(dialect, "Generate ANSI-standard SQL."),
    )
