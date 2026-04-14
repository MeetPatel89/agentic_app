from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SchemaContextFormat(StrEnum):
    compact_ddl = "compact_ddl"
    structured_catalog = "structured_catalog"
    concise_notation = "concise_notation"


class ForeignKeyInfo(BaseModel):
    column_name: str
    referenced_schema: str | None = None
    referenced_table: str
    referenced_column: str | None = None
    constraint_name: str | None = None


class ColumnDetail(BaseModel):
    name: str
    data_type: str | None = None
    nullable: bool | None = None
    default: str | None = None
    is_primary_key: bool = False
    description: str | None = None


class TableDetail(BaseModel):
    name: str
    schema_name: str | None = None
    columns: list[ColumnDetail] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)
    description: str | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.name}" if self.schema_name else self.name


class SchemaCatalog(BaseModel):
    backend: str
    tables: list[TableDetail] = Field(default_factory=list)


class SchemaContextResponse(BaseModel):
    format: SchemaContextFormat
    schema_text: str
    table_count: int
    estimated_tokens: int
