from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter
from app.database import get_db
from app.models import Run
from app.schemas import ChatRequest, NormalizedChatResponse, StreamDelta, StreamError, StreamFinal, StreamMeta

logger = logging.getLogger("llm_router")

router = APIRouter(prefix="/api")


async def _persist_run(
    db: AsyncSession,
    req: ChatRequest,
    response: NormalizedChatResponse | None,
    error: str | None,
    latency_ms: float,
) -> Run:
    run = Run(
        provider=req.provider,
        model=req.model,
        request_json=req.model_dump_json(),
        normalized_response_json=response.model_dump_json() if response else None,
        raw_response_json=json.dumps(response.raw) if response else None,
        status="success" if response else "error",
        error_message=error,
        latency_ms=latency_ms,
        prompt_tokens=response.usage.prompt_tokens if response else None,
        completion_tokens=response.usage.completion_tokens if response else None,
        total_tokens=response.usage.total_tokens if response else None,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> dict:
    adapter = get_adapter(req.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    start = time.perf_counter()
    try:
        response = await adapter.chat(req)
        latency = (time.perf_counter() - start) * 1000
        run = await _persist_run(db, req, response, None, latency)
        return {"run_id": run.id, "response": response.model_dump(), "latency_ms": latency}
    except NotImplementedError as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_run(db, req, None, str(exc), latency)
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_run(db, req, None, str(exc), latency)
        logger.exception("Chat error for provider=%s", req.provider)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    adapter = get_adapter(req.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    start = time.perf_counter()

    async def event_generator() -> AsyncIterator[str]:
        final_response: NormalizedChatResponse | None = None
        error_msg: str | None = None
        try:
            async for event in adapter.stream_chat(req):
                if isinstance(event, StreamDelta):
                    yield f"event: delta\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StreamMeta):
                    yield f"event: meta\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StreamFinal):
                    final_response = event.response
                    yield f"event: final\ndata: {event.model_dump_json()}\n\n"
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
                await _persist_run(db, req, final_response, error_msg, latency)
            except Exception:
                logger.exception("Failed to persist streaming run")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
