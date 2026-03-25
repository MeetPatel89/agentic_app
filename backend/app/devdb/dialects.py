from __future__ import annotations

import re
from urllib.parse import urlparse

from app.devdb.schemas import DatabaseBackend

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def detect_backend(connection_string: str) -> DatabaseBackend:
    scheme = urlparse(connection_string).scheme
    if scheme.startswith("sqlite"):
        return "sqlite"
    if scheme.startswith("postgresql"):
        return "postgresql"
    if scheme.startswith("mssql"):
        return "mssql"
    return "generic"


def validate_identifier(value: str, kind: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {kind} identifier: '{value}'")
    return value


def list_tables_sql(backend: DatabaseBackend) -> str:
    if backend == "sqlite":
        return (
            "SELECT name AS table_name, NULL AS table_schema "
            "FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    if backend == "postgresql":
        return (
            "SELECT table_name, table_schema "
            "FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' "
            "AND table_schema NOT IN ('pg_catalog', 'information_schema') "
            "ORDER BY table_schema, table_name"
        )
    if backend == "mssql":
        return (
            "SELECT TABLE_NAME AS table_name, TABLE_SCHEMA AS table_schema "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME"
        )
    return (
        "SELECT table_name, table_schema "
        "FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' "
        "ORDER BY table_schema, table_name"
    )
