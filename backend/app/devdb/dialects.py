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


def foreign_keys_sql(backend: DatabaseBackend) -> tuple[str, dict[str, str]] | None:
    """Return (sql, named-params template hints) for listing FKs for a table.

    Callers substitute :table_name / :schema_name as bind params.
    Returns None for SQLite — callers should use PRAGMA instead (see foreign_keys_pragma_sql).
    """
    if backend == "sqlite":
        return None
    if backend == "postgresql":
        sql = (
            "SELECT "
            "    tc.constraint_name AS constraint_name, "
            "    kcu.column_name AS column_name, "
            "    ccu.table_schema AS referenced_schema, "
            "    ccu.table_name AS referenced_table, "
            "    ccu.column_name AS referenced_column "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "    ON tc.constraint_name = kcu.constraint_name "
            "    AND tc.table_schema = kcu.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "    ON ccu.constraint_name = tc.constraint_name "
            "    AND ccu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "    AND tc.table_name = :table_name "
            "    AND (:schema_name IS NULL OR tc.table_schema = :schema_name) "
            "ORDER BY tc.constraint_name, kcu.ordinal_position"
        )
        return sql, {}
    if backend == "mssql":
        sql = (
            "SELECT "
            "    fk.name AS constraint_name, "
            "    col_parent.name AS column_name, "
            "    sch_ref.name AS referenced_schema, "
            "    tab_ref.name AS referenced_table, "
            "    col_ref.name AS referenced_column "
            "FROM sys.foreign_keys fk "
            "JOIN sys.foreign_key_columns fkc "
            "    ON fkc.constraint_object_id = fk.object_id "
            "JOIN sys.tables tab_parent ON tab_parent.object_id = fkc.parent_object_id "
            "JOIN sys.schemas sch_parent ON sch_parent.schema_id = tab_parent.schema_id "
            "JOIN sys.columns col_parent "
            "    ON col_parent.object_id = fkc.parent_object_id "
            "    AND col_parent.column_id = fkc.parent_column_id "
            "JOIN sys.tables tab_ref ON tab_ref.object_id = fkc.referenced_object_id "
            "JOIN sys.schemas sch_ref ON sch_ref.schema_id = tab_ref.schema_id "
            "JOIN sys.columns col_ref "
            "    ON col_ref.object_id = fkc.referenced_object_id "
            "    AND col_ref.column_id = fkc.referenced_column_id "
            "WHERE tab_parent.name = :table_name "
            "    AND (:schema_name IS NULL OR sch_parent.name = :schema_name) "
            "ORDER BY fk.name, fkc.constraint_column_id"
        )
        return sql, {}
    # generic fallback — info_schema
    sql = (
        "SELECT "
        "    tc.constraint_name AS constraint_name, "
        "    kcu.column_name AS column_name, "
        "    kcu.referenced_table_schema AS referenced_schema, "
        "    kcu.referenced_table_name AS referenced_table, "
        "    kcu.referenced_column_name AS referenced_column "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "    ON tc.constraint_name = kcu.constraint_name "
        "WHERE tc.constraint_type = 'FOREIGN KEY' "
        "    AND tc.table_name = :table_name "
        "    AND (:schema_name IS NULL OR tc.table_schema = :schema_name) "
        "ORDER BY tc.constraint_name, kcu.ordinal_position"
    )
    return sql, {}


def foreign_keys_pragma_sql(safe_table: str) -> str:
    """SQLite-only: returns the PRAGMA call for listing FKs on a table.

    safe_table MUST be pre-validated via validate_identifier — it is interpolated
    directly because SQLite PRAGMA does not accept bind parameters.
    """
    return f'PRAGMA foreign_key_list("{safe_table}")'


def primary_keys_sql(backend: DatabaseBackend) -> str | None:
    """Return SQL to list PK column names for a table.

    Returns None for SQLite — PRAGMA table_info already exposes the pk flag.
    """
    if backend == "sqlite":
        return None
    if backend == "postgresql":
        return (
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "    ON tc.constraint_name = kcu.constraint_name "
            "    AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            "    AND tc.table_name = :table_name "
            "    AND (:schema_name IS NULL OR tc.table_schema = :schema_name) "
            "ORDER BY kcu.ordinal_position"
        )
    if backend == "mssql":
        return (
            "SELECT col.name AS column_name "
            "FROM sys.indexes idx "
            "JOIN sys.index_columns ic "
            "    ON ic.object_id = idx.object_id AND ic.index_id = idx.index_id "
            "JOIN sys.columns col "
            "    ON col.object_id = ic.object_id AND col.column_id = ic.column_id "
            "JOIN sys.tables tab ON tab.object_id = idx.object_id "
            "JOIN sys.schemas sch ON sch.schema_id = tab.schema_id "
            "WHERE idx.is_primary_key = 1 "
            "    AND tab.name = :table_name "
            "    AND (:schema_name IS NULL OR sch.name = :schema_name) "
            "ORDER BY ic.key_ordinal"
        )
    return (
        "SELECT kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "    ON tc.constraint_name = kcu.constraint_name "
        "WHERE tc.constraint_type = 'PRIMARY KEY' "
        "    AND tc.table_name = :table_name "
        "    AND (:schema_name IS NULL OR tc.table_schema = :schema_name) "
        "ORDER BY kcu.ordinal_position"
    )


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
