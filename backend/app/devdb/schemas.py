from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DatabaseBackend = Literal["sqlite", "postgresql", "mssql", "generic"]


class TableInfo(BaseModel):
    name: str
    schema_name: str | None = None


class ColumnInfo(BaseModel):
    name: str
    data_type: str | None = None
    nullable: bool | None = None
    default: str | None = None
    is_primary_key: bool = False


class ListTablesResponse(BaseModel):
    backend: DatabaseBackend
    tables: list[TableInfo]


class DescribeTableResponse(BaseModel):
    backend: DatabaseBackend
    table: str
    schema_name: str | None = None
    columns: list[ColumnInfo]


class DevDBQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    connection_string: str | None = None
    timeout_seconds: int = Field(default=15, ge=1, le=120)
    max_rows: int = Field(default=200, ge=1, le=5000)


class DevDBQueryResponse(BaseModel):
    backend: DatabaseBackend
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool = False
