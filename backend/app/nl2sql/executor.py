from __future__ import annotations

import logging
import time

import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlglot import errors as sqlglot_errors
from sqlglot import exp

from app.config import get_settings
from app.nl2sql.schemas import SQLDialect, SQLExecuteRequest, SQLExecuteResponse

logger = logging.getLogger(__name__)
_DIALECT_TO_SQLGLOT: dict[SQLDialect, str] = {
    SQLDialect.postgresql: "postgres",
    SQLDialect.tsql: "tsql",
    SQLDialect.mysql: "mysql",
    SQLDialect.sqlite: "sqlite",
    SQLDialect.bigquery: "bigquery",
    SQLDialect.snowflake: "snowflake",
}


async def execute_sql(request: SQLExecuteRequest) -> SQLExecuteResponse:
    """Execute validated SQL against the configured application database.

    Uses the resolved database URL from app settings. The engine is created with
    a bounded pool (1 connection) and disposed immediately after execution.
    """
    _validate_execute_request(request)
    connection_string = get_settings().resolved_database_url

    engine = create_async_engine(
        connection_string,
        pool_size=1,
        max_overflow=0,
        pool_timeout=request.timeout_seconds,
        echo=False,
    )

    try:
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            start = time.perf_counter()
            result = await session.execute(text(request.sql).execution_options(timeout=request.timeout_seconds))
            elapsed_ms = (time.perf_counter() - start) * 1000

            columns = list(result.keys())
            all_rows = result.fetchall()

            truncated = len(all_rows) > request.max_rows
            rows = [list(row) for row in all_rows[: request.max_rows]]

            return SQLExecuteResponse(
                columns=columns,
                rows=rows,
                row_count=len(all_rows),
                execution_time_ms=round(elapsed_ms, 2),
                truncated=truncated,
            )
    finally:
        await engine.dispose()


def _validate_execute_request(request: SQLExecuteRequest) -> None:
    dialect = _DIALECT_TO_SQLGLOT.get(request.dialect)
    if not dialect:
        raise ValueError(f"Unsupported SQL dialect: {request.dialect}")

    sql_text = request.sql.strip()
    try:
        raw_statements = sqlglot.parse(sql_text, read=dialect)
    except sqlglot_errors.ParseError as exc:
        raise ValueError(f"SQL parse failed for execution: {exc}") from exc

    # Filter out None entries and bare Semicolon nodes (produced by sqlglot
    # when trailing comments follow a semicolon, e.g. "SELECT 1;\n-- note").
    statements = [s for s in raw_statements if s is not None and not isinstance(s, exp.Semicolon)]

    if len(statements) != 1:
        raise ValueError("Execution requires exactly one SQL statement")

    statement = statements[0]
    if request.read_only and not isinstance(statement, (exp.Select, exp.Union, exp.With)):
        raise ValueError("Read-only execution mode only allows SELECT queries")
