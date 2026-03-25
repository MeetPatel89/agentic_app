from __future__ import annotations

import re
import time
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.database import create_app_engine
from app.devdb.dialects import detect_backend, list_tables_sql, validate_identifier
from app.devdb.schemas import (
    ColumnInfo,
    DescribeTableResponse,
    DevDBQueryRequest,
    DevDBQueryResponse,
    ListTablesResponse,
    TableInfo,
)

_ALLOWED_SQL_PREFIXES = ("select", "with", "explain", "show", "pragma")
_MUTATING_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|merge|grant|revoke|call)\b",
    flags=re.IGNORECASE,
)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class DevDBError(RuntimeError):
    pass


class DevDBService:
    def ensure_enabled(self) -> None:
        if not get_settings().dev_db_tools_enabled:
            raise DevDBError("Developer DB tools are disabled. Set DEV_DB_TOOLS_ENABLED=true to enable them.")

    async def list_tables(
        self,
        *,
        connection_string: str | None = None,
        max_tables: int = 1000,
    ) -> ListTablesResponse:
        conn_str = self._resolve_connection_string(connection_string)
        backend = detect_backend(conn_str)
        engine = create_app_engine(conn_str)

        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as session:
                result = await session.execute(text(list_tables_sql(backend)))
                rows = result.mappings().all()
                items = [
                    TableInfo(name=str(row["table_name"]), schema_name=row.get("table_schema"))
                    for row in rows[:max_tables]
                ]
                return ListTablesResponse(backend=backend, tables=items)
        except SQLAlchemyError as exc:
            raise DevDBError(f"Failed to list tables: {exc.__class__.__name__}") from exc
        finally:
            await engine.dispose()

    async def describe_table(
        self,
        *,
        table_name: str,
        schema_name: str | None = None,
        connection_string: str | None = None,
    ) -> DescribeTableResponse:
        conn_str = self._resolve_connection_string(connection_string)
        backend = detect_backend(conn_str)

        safe_table = validate_identifier(table_name, "table")
        safe_schema = validate_identifier(schema_name, "schema") if schema_name else None

        engine = create_app_engine(conn_str)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as session:
                if backend == "sqlite":
                    query = text(f'PRAGMA table_info("{safe_table}")')
                    result = await session.execute(query)
                    rows = result.mappings().all()
                    columns = [
                        ColumnInfo(
                            name=str(row["name"]),
                            data_type=row.get("type"),
                            nullable=not bool(row.get("notnull")),
                            default=self._to_string_or_none(row.get("dflt_value")),
                            is_primary_key=bool(row.get("pk")),
                        )
                        for row in rows
                    ]
                else:
                    query = (
                        "SELECT column_name, data_type, is_nullable, column_default "
                        "FROM information_schema.columns "
                        "WHERE table_name = :table_name "
                    )
                    params: dict[str, str] = {"table_name": safe_table}
                    if safe_schema:
                        query += "AND table_schema = :schema_name "
                        params["schema_name"] = safe_schema
                    query += "ORDER BY ordinal_position"

                    result = await session.execute(text(query), params)
                    rows = result.mappings().all()
                    columns = [
                        ColumnInfo(
                            name=str(row["column_name"]),
                            data_type=self._to_string_or_none(row.get("data_type")),
                            nullable=self._nullable_value(row.get("is_nullable")),
                            default=self._to_string_or_none(row.get("column_default")),
                            is_primary_key=False,
                        )
                        for row in rows
                    ]

                return DescribeTableResponse(
                    backend=backend,
                    table=safe_table,
                    schema_name=safe_schema,
                    columns=columns,
                )
        except SQLAlchemyError as exc:
            raise DevDBError(f"Failed to describe table: {exc.__class__.__name__}") from exc
        finally:
            await engine.dispose()

    async def query(self, request: DevDBQueryRequest) -> DevDBQueryResponse:
        conn_str = self._resolve_connection_string(request.connection_string)
        backend = detect_backend(conn_str)
        self._validate_read_only_sql(request.sql)

        engine = create_app_engine(conn_str)
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
                rows = [
                    [self._normalize_value(value) for value in row]
                    for row in all_rows[: request.max_rows]
                ]

                return DevDBQueryResponse(
                    backend=backend,
                    columns=columns,
                    rows=rows,
                    row_count=len(all_rows),
                    execution_time_ms=round(elapsed_ms, 2),
                    truncated=truncated,
                )
        except SQLAlchemyError as exc:
            raise DevDBError(f"Query failed: {exc.__class__.__name__}") from exc
        finally:
            await engine.dispose()

    @staticmethod
    def _to_string_or_none(value: object | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _nullable_value(value: object | None) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() in {"YES", "TRUE", "1"}
        if isinstance(value, int):
            return value == 1
        return None

    @staticmethod
    def _normalize_value(value: object) -> object:
        if isinstance(value, (datetime, date, dt_time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _validate_read_only_sql(sql: str) -> None:
        normalized = sql.strip()
        if not normalized:
            raise DevDBError("SQL is empty.")

        # Only single statement execution is allowed.
        if normalized.endswith(";"):
            normalized = normalized[:-1].strip()
        if ";" in normalized:
            raise DevDBError("Only a single SQL statement is allowed.")

        lowered = normalized.lower()
        if not lowered.startswith(_ALLOWED_SQL_PREFIXES):
            raise DevDBError(
                "Only read-only statements are allowed (SELECT, WITH, EXPLAIN, SHOW, PRAGMA)."
            )

        if _MUTATING_SQL_RE.search(normalized):
            raise DevDBError("Mutating SQL keywords are not allowed in developer query mode.")

    def _resolve_connection_string(self, connection_string: str | None) -> str:
        self.ensure_enabled()
        settings = get_settings()
        conn_str = connection_string or settings.database_url
        self._validate_localhost_if_required(conn_str, settings.dev_db_tools_require_localhost)
        return conn_str

    @staticmethod
    def _validate_localhost_if_required(connection_string: str, require_localhost: bool) -> None:
        if not require_localhost:
            return

        backend = detect_backend(connection_string)
        if backend == "sqlite":
            return

        host = (urlparse(connection_string).hostname or "").lower()
        if host not in _LOCAL_HOSTS:
            raise DevDBError(
                "Non-localhost database connections are blocked. "
                "Set DEV_DB_TOOLS_REQUIRE_LOCALHOST=false to allow remote hosts."
            )
