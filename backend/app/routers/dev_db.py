from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.devdb.schemas import DescribeTableResponse, DevDBQueryRequest, DevDBQueryResponse, ListTablesResponse
from app.devdb.service import DevDBError, DevDBService
from app.nl2sql.schema_context import SchemaContextFormat, SchemaContextResponse, SchemaContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev/db", tags=["dev-db"])
dev_db_service = DevDBService()
schema_context_service = SchemaContextService(devdb_service=dev_db_service)


def _ensure_dev_db_enabled() -> None:
    try:
        dev_db_service.ensure_enabled()
    except DevDBError as exc:
        # Hide route existence when disabled.
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tables", response_model=ListTablesResponse)
async def list_tables(
    _: None = Depends(_ensure_dev_db_enabled),
    max_tables: int = Query(default=1000, ge=1, le=5000),
) -> ListTablesResponse:
    try:
        return await dev_db_service.list_tables(max_tables=max_tables)
    except DevDBError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/table/{table_name}", response_model=DescribeTableResponse)
async def describe_table(
    table_name: str,
    _: None = Depends(_ensure_dev_db_enabled),
    schema_name: str | None = Query(default=None),
) -> DescribeTableResponse:
    try:
        return await dev_db_service.describe_table(table_name=table_name, schema_name=schema_name)
    except DevDBError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/schema-context", response_model=SchemaContextResponse)
async def schema_context(
    _: None = Depends(_ensure_dev_db_enabled),
    format: SchemaContextFormat = Query(default=SchemaContextFormat.compact_ddl),
    tables: str | None = Query(
        default=None,
        description="Comma-separated list of table names or schema.table to include.",
    ),
    include_foreign_keys: bool = Query(default=True),
) -> SchemaContextResponse:
    table_filter = None
    if tables:
        table_filter = [entry.strip() for entry in tables.split(",") if entry.strip()]
    try:
        return await schema_context_service.generate(
            fmt=format,
            table_filter=table_filter,
            include_foreign_keys=include_foreign_keys,
        )
    except DevDBError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Schema context generation failed")
        raise HTTPException(status_code=502, detail="Failed to build schema context.") from exc


@router.post("/query", response_model=DevDBQueryResponse)
async def run_query(
    request: DevDBQueryRequest,
    _: None = Depends(_ensure_dev_db_enabled),
) -> DevDBQueryResponse:
    try:
        return await dev_db_service.query(request)
    except DevDBError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Developer DB query route failed")
        raise HTTPException(status_code=502, detail="Developer DB query failed.") from exc
