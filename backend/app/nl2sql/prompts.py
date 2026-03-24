from __future__ import annotations

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

## Rules
1. Return ONLY the SQL query — no markdown fences, no commentary before or after the query.
2. After the SQL, on a new line starting with "-- Explanation:", provide a brief explanation \
of the query logic.
3. Use meaningful table aliases.
4. Prefer explicit JOINs over implicit comma-joins.
5. Always qualify column names with table aliases when the query involves multiple tables.
6. Use parameterized-style placeholders ($1, :param, or ?) only if the question implies user input.
7. Avoid SELECT * in production queries — select only needed columns.
8. Use CTEs (WITH clauses) for complex multi-step queries for readability.
9. Add appropriate WHERE clauses for safety on UPDATE/DELETE statements.

## SQL Dialect
{dialect_guidance}

## Output Format
<SQL query>
-- Explanation: <brief description of what the query does and why>
"""


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
