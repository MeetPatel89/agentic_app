from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter
from app.database import get_db
from app.models import Run
from app.nl2sql import executor, service
from app.nl2sql.sandbox import validate_syntax, validate_with_sandbox
from app.nl2sql.schemas import (
    NL2SQLRequest,
    NL2SQLResponse,
    NL2SQLStreamFinal,
    SQLExecuteRequest,
    SQLExecuteResponse,
    SQLValidateRequest,
    SQLValidationResult,
)
from app.schemas import StreamDelta, StreamError, StreamMeta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/querylab", tags=["querylab"])


async def _persist_querylab_run(
    db: AsyncSession,
    request: NL2SQLRequest,
    response: NL2SQLResponse | None,
    error: str | None,
    latency_ms: float,
) -> Run:
    run = Run(
        provider=request.provider,
        model=request.model,
        request_json=request.model_dump_json(),
        normalized_response_json=response.model_dump_json() if response else None,
        status="success" if response else "error",
        error_message=error,
        latency_ms=latency_ms,
        prompt_tokens=response.usage.get("prompt_tokens") if response else None,
        completion_tokens=response.usage.get("completion_tokens") if response else None,
        total_tokens=response.usage.get("total_tokens") if response else None,
        tags="querylab",
    )
    db.add(run)
    await db.flush()
    return run


@router.post("/generate", response_model=NL2SQLResponse)
async def generate(
    req: NL2SQLRequest,
    db: AsyncSession = Depends(get_db),
) -> NL2SQLResponse:
    adapter = get_adapter(req.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    start = time.perf_counter()
    try:
        response = await service.generate_sql(req, adapter)
        latency = (time.perf_counter() - start) * 1000
        response.latency_ms = round(latency, 2)
        run = await _persist_querylab_run(db, req, response, None, latency)
        response.run_id = run.id
        await db.commit()
        return response
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_querylab_run(db, req, None, str(exc), latency)
        await db.commit()
        logger.exception("QueryLab generate error for provider=%s", req.provider)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/generate/stream")
async def generate_stream(
    req: NL2SQLRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    adapter = get_adapter(req.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    start = time.perf_counter()

    async def event_generator() -> AsyncIterator[str]:
        nl2sql_response: NL2SQLResponse | None = None
        error_msg: str | None = None
        try:
            async for event in service.stream_generate_sql(req, adapter):
                if isinstance(event, StreamDelta):
                    yield f"event: delta\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StreamMeta):
                    yield f"event: meta\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, NL2SQLStreamFinal):
                    latency = (time.perf_counter() - start) * 1000
                    nl2sql_response = NL2SQLResponse(
                        generated_sql=event.generated_sql,
                        explanation=event.explanation,
                        dialect=event.dialect,
                        validation=event.validation,
                        usage=event.usage,
                        latency_ms=round(latency, 2),
                    )
                    yield f"event: querylab_final\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StreamError):
                    error_msg = event.message
                    yield f"event: error\ndata: {event.model_dump_json()}\n\n"
        except Exception as exc:
            error_msg = str(exc)
            err = StreamError(message=error_msg)
            yield f"event: error\ndata: {err.model_dump_json()}\n\n"
        finally:
            latency = (time.perf_counter() - start) * 1000
            try:
                run = await _persist_querylab_run(db, req, nl2sql_response, error_msg, latency)
                if nl2sql_response:
                    nl2sql_response.run_id = run.id
                await db.commit()
            except Exception:
                logger.exception("Failed to persist QueryLab streaming run")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/validate", response_model=SQLValidationResult)
async def validate(req: SQLValidateRequest) -> SQLValidationResult:
    if req.sandbox_ddl:
        return validate_with_sandbox(req.sql, req.dialect, req.sandbox_ddl)
    return validate_syntax(req.sql, req.dialect)


@router.post("/execute", response_model=SQLExecuteResponse)
async def execute(req: SQLExecuteRequest) -> SQLExecuteResponse:
    try:
        return await executor.execute_sql(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("QueryLab execute error")
        raise HTTPException(status_code=502, detail=f"Execution failed: {exc}")
