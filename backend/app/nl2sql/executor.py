from __future__ import annotations

import logging
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.nl2sql.schemas import SQLExecuteRequest, SQLExecuteResponse

logger = logging.getLogger(__name__)

_SUPPORTED_SCHEMES = {
    "postgresql+asyncpg",
    "mysql+aiomysql",
    "sqlite+aiosqlite",
}


async def execute_sql(request: SQLExecuteRequest) -> SQLExecuteResponse:
    """Execute validated SQL against a real database via a temporary async engine.

    Connection strings are never persisted or logged. The engine is created with
    a bounded pool (1 connection) and disposed immediately after execution.
    """
    _validate_connection_string(request.connection_string)

    engine = create_async_engine(
        request.connection_string,
        pool_size=1,
        max_overflow=0,
        pool_timeout=request.timeout_seconds,
        echo=False,
    )

    try:
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            start = time.perf_counter()
            result = await session.execute(
                text(request.sql).execution_options(timeout=request.timeout_seconds)
            )
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


def _validate_connection_string(conn_str: str) -> None:
    """Basic validation of the connection string scheme."""
    scheme = conn_str.split("://")[0] if "://" in conn_str else ""
    if scheme not in _SUPPORTED_SCHEMES:
        supported = ", ".join(sorted(_SUPPORTED_SCHEMES))
        raise ValueError(
            f"Unsupported connection scheme '{scheme}'. Supported: {supported}"
        )
