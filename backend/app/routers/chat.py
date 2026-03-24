from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter
from app.agentic.tools import tool_registry
from app.agentic.traces import new_trace
from app.database import get_db
from app.models import Run
from app.schemas import (
    ChatRequest,
    ConversationTurnRequest,
    NormalizedChatResponse,
    StreamDelta,
    StreamError,
    StreamFinal,
    StreamMeta,
    TurnResponse,
)
from app.services.conversation import conversation_service
from app.services.tool_executor import ToolExecutor

logger = logging.getLogger("llm_router")

router = APIRouter(prefix="/api")


async def _persist_run(
    db: AsyncSession,
    req: ChatRequest,
    response: NormalizedChatResponse | None,
    error: str | None,
    latency_ms: float,
    *,
    trace_id: str | None = None,
    parent_run_id: str | None = None,
    conversation_id: str | None = None,
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
        trace_id=trace_id,
        parent_run_id=parent_run_id,
        conversation_id=conversation_id,
    )
    db.add(run)
    await db.flush()
    return run


# ── Legacy single-shot endpoints (unchanged contract) ──────────────────────

@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> dict:
    adapter = get_adapter(req.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    start = time.perf_counter()
    try:
        if req.tools:
            executor = ToolExecutor(tool_registry)
            response = await executor.execute_with_tools(adapter, req)
        else:
            response = await adapter.chat(req)
        latency = (time.perf_counter() - start) * 1000
        run = await _persist_run(db, req, response, None, latency)
        await db.commit()
        return {"run_id": run.id, "response": response.model_dump(), "latency_ms": latency}
    except NotImplementedError as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_run(db, req, None, str(exc), latency)
        await db.commit()
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_run(db, req, None, str(exc), latency)
        await db.commit()
        logger.exception("Chat error for provider=%s", req.provider)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    if req.tools:
        raise HTTPException(status_code=400, detail="Tool calling is not supported with streaming yet")
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
                await db.commit()
            except Exception:
                logger.exception("Failed to persist streaming run")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Turn-based conversation endpoints ──────────────────────────────────────

async def _prepare_turn(
    db: AsyncSession, req: ConversationTurnRequest
) -> tuple:
    """Shared setup for turn and turn/stream: resolve or create conversation, build ChatRequest."""
    svc = conversation_service

    if req.conversation_id:
        conv = await svc.get_conversation(db, req.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = await svc.create_conversation(
            db,
            provider=req.provider,
            model=req.model,
            system_prompt=req.system_prompt,
        )

    chat_req = await svc.build_chat_request(
        db,
        conversation=conv,
        new_user_message=req.message,
        provider=req.provider,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        provider_options=req.provider_options,
    )

    await svc.append_message(db, conversation_id=conv.id, role="user", content=req.message)

    # Resolve tools based on tool_mode
    tool_defs: list = []
    if req.tool_mode == "auto":
        tool_defs = tool_registry.list_request_schemas()
    elif req.tool_mode == "manual" and req.tool_names:
        for name in req.tool_names:
            tool = tool_registry.get(name)
            if tool is None:
                raise HTTPException(status_code=400, detail=f"Unknown tool: '{name}'")
            tool_defs.append(tool.as_request_schema())

    if tool_defs:
        chat_req = chat_req.model_copy(update={"tools": tool_defs, "tool_choice": "auto"})

    adapter = get_adapter(req.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' not available")

    trace = new_trace()
    parent_run_id = await svc.get_last_run_id(db, conv.id)

    return conv, chat_req, adapter, trace, parent_run_id


@router.post("/chat/turn", response_model=TurnResponse)
async def chat_turn(
    req: ConversationTurnRequest, db: AsyncSession = Depends(get_db)
) -> TurnResponse:
    conv, chat_req, adapter, trace, parent_run_id = await _prepare_turn(db, req)
    svc = conversation_service

    start = time.perf_counter()
    try:
        if chat_req.tools:
            executor = ToolExecutor(tool_registry)
            response = await executor.execute_with_tools(adapter, chat_req)
        else:
            response = await adapter.chat(chat_req)
        latency = (time.perf_counter() - start) * 1000

        run = await _persist_run(
            db, chat_req, response, None, latency,
            trace_id=trace.trace_id,
            parent_run_id=parent_run_id,
            conversation_id=conv.id,
        )
        await svc.append_message(
            db, conversation_id=conv.id, role="assistant", content=response.output_text, run_id=run.id,
        )
        await db.commit()

        return TurnResponse(
            conversation_id=conv.id, run_id=run.id, response=response, latency_ms=latency,
        )
    except NotImplementedError as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_run(
            db, chat_req, None, str(exc), latency,
            trace_id=trace.trace_id, parent_run_id=parent_run_id, conversation_id=conv.id,
        )
        await db.commit()
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        await _persist_run(
            db, chat_req, None, str(exc), latency,
            trace_id=trace.trace_id, parent_run_id=parent_run_id, conversation_id=conv.id,
        )
        await db.commit()
        logger.exception("Chat turn error for provider=%s", conv.provider)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/chat/turn/stream")
async def chat_turn_stream(
    req: ConversationTurnRequest, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    if req.tool_mode == "auto" or (req.tool_mode == "manual" and req.tool_names):
        raise HTTPException(status_code=400, detail="Tool calling is not supported with streaming")
    conv, chat_req, adapter, trace, parent_run_id = await _prepare_turn(db, req)
    svc = conversation_service

    start = time.perf_counter()

    async def event_generator() -> AsyncIterator[str]:
        final_response: NormalizedChatResponse | None = None
        error_msg: str | None = None
        collected_text = ""
        try:
            async for event in adapter.stream_chat(chat_req):
                if isinstance(event, StreamDelta):
                    collected_text += event.text
                    yield f"event: delta\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StreamMeta):
                    yield f"event: meta\ndata: {event.model_dump_json()}\n\n"
                elif isinstance(event, StreamFinal):
                    final_response = event.response
                    final_with_ids = StreamFinal(
                        response=event.response,
                        conversation_id=conv.id,
                    )
                    yield f"event: final\ndata: {final_with_ids.model_dump_json()}\n\n"
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
                run = await _persist_run(
                    db, chat_req, final_response, error_msg, latency,
                    trace_id=trace.trace_id,
                    parent_run_id=parent_run_id,
                    conversation_id=conv.id,
                )
                if final_response:
                    await svc.append_message(
                        db, conversation_id=conv.id, role="assistant",
                        content=final_response.output_text, run_id=run.id,
                    )
                elif collected_text:
                    await svc.append_message(
                        db, conversation_id=conv.id, role="assistant",
                        content=collected_text, run_id=run.id,
                    )
                await db.commit()
            except Exception:
                logger.exception("Failed to persist streaming turn run")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
