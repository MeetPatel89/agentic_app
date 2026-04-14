from __future__ import annotations

from app.devdb.service import DevDBService
from app.nl2sql.schema_context.formatters import estimate_tokens, format_schema_context
from app.nl2sql.schema_context.introspector import SchemaIntrospector
from app.nl2sql.schema_context.models import (
    SchemaCatalog,
    SchemaContextFormat,
    SchemaContextResponse,
)


class SchemaContextService:
    """Composes the introspector + formatter to produce prompt-ready schema text."""

    def __init__(
        self,
        *,
        devdb_service: DevDBService | None = None,
        introspector: SchemaIntrospector | None = None,
    ) -> None:
        self._devdb_service = devdb_service or DevDBService()
        self._introspector = introspector or SchemaIntrospector(self._devdb_service)

    async def generate(
        self,
        *,
        fmt: SchemaContextFormat = SchemaContextFormat.compact_ddl,
        connection_string: str | None = None,
        table_filter: list[str] | None = None,
        include_foreign_keys: bool = True,
    ) -> SchemaContextResponse:
        catalog = await self._introspector.introspect(
            connection_string=connection_string,
            table_filter=table_filter,
            include_foreign_keys=include_foreign_keys,
        )
        return self.format_catalog(catalog, fmt=fmt)

    @staticmethod
    def format_catalog(
        catalog: SchemaCatalog,
        *,
        fmt: SchemaContextFormat = SchemaContextFormat.compact_ddl,
    ) -> SchemaContextResponse:
        schema_text = format_schema_context(catalog, fmt)
        return SchemaContextResponse(
            format=fmt,
            schema_text=schema_text,
            table_count=len(catalog.tables),
            estimated_tokens=estimate_tokens(schema_text),
        )
