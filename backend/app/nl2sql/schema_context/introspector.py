from __future__ import annotations

import asyncio

from app.devdb.service import DevDBService
from app.nl2sql.schema_context.models import (
    ColumnDetail,
    ForeignKeyInfo,
    SchemaCatalog,
    TableDetail,
)


class SchemaIntrospector:
    """Builds a SchemaCatalog from a live database via DevDBService."""

    def __init__(
        self,
        service: DevDBService | None = None,
        *,
        max_concurrency: int = 10,
    ) -> None:
        self._service = service or DevDBService()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def introspect(
        self,
        *,
        connection_string: str | None = None,
        table_filter: list[str] | None = None,
        include_foreign_keys: bool = True,
    ) -> SchemaCatalog:
        tables_response = await self._service.list_tables(connection_string=connection_string)
        backend = tables_response.backend

        allowed: set[str] | None = None
        if table_filter:
            allowed = {name.lower() for name in table_filter}

        selected = [
            table
            for table in tables_response.tables
            if allowed is None
            or table.name.lower() in allowed
            or _qualified(table.schema_name, table.name).lower() in allowed
        ]

        async def _describe_one(name: str, schema_name: str | None) -> TableDetail:
            async with self._semaphore:
                describe = await self._service.describe_table(
                    table_name=name,
                    schema_name=schema_name,
                    connection_string=connection_string,
                )
                columns = [
                    ColumnDetail(
                        name=col.name,
                        data_type=col.data_type,
                        nullable=col.nullable,
                        default=col.default,
                        is_primary_key=col.is_primary_key,
                    )
                    for col in describe.columns
                ]

                fks: list[ForeignKeyInfo] = []
                if include_foreign_keys:
                    fk_rows = await self._service.list_foreign_keys(
                        table_name=name,
                        schema_name=schema_name,
                        connection_string=connection_string,
                    )
                    fks = [
                        ForeignKeyInfo(
                            column_name=str(row["column_name"]),
                            referenced_schema=row.get("referenced_schema"),
                            referenced_table=str(row["referenced_table"]),
                            referenced_column=row.get("referenced_column"),
                            constraint_name=row.get("constraint_name"),
                        )
                        for row in fk_rows
                    ]

                return TableDetail(
                    name=name,
                    schema_name=schema_name,
                    columns=columns,
                    foreign_keys=fks,
                )

        details = await asyncio.gather(*(_describe_one(t.name, t.schema_name) for t in selected))

        return SchemaCatalog(backend=backend, tables=list(details))


def _qualified(schema: str | None, name: str) -> str:
    return f"{schema}.{name}" if schema else name
