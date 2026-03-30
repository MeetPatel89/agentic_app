from __future__ import annotations

import inspect
import json
import logging
import re
from collections.abc import AsyncIterator, Awaitable
from typing import Any, cast

from app.adapters.base import ProviderAdapter, StreamEvent
from app.nl2sql.prompts import NL2SQL_JSON_SCHEMA, RESPONSE_FORMAT_PROVIDERS, build_system_prompt
from app.nl2sql.sandbox import validate_syntax, validate_with_sandbox
from app.nl2sql.schemas import (
    NL2SQLRequest,
    NL2SQLResponse,
    NL2SQLStreamFinal,
    SQLDialect,
    SQLQuery,
    SQLValidationResult,
)
from app.schemas import ChatRequest, Message, StreamDelta, StreamError, StreamFinal, StreamMeta

logger = logging.getLogger(__name__)


async def generate_sql(
    request: NL2SQLRequest,
    adapter: ProviderAdapter,
) -> NL2SQLResponse:
    """Generate SQL from natural language, then validate via sandbox."""
    chat_req = _build_chat_request(request)
    response = await adapter.chat(chat_req)

    raw_text = response.output_text
    parsed = _parse_llm_response(raw_text, request.dialect)

    recommended = parsed["queries"][parsed["recommended_index"]]
    validation = _run_validation(recommended["sql"], request.dialect, request.sandbox_ddl)

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }

    queries = [SQLQuery(**q) for q in parsed["queries"]]

    return NL2SQLResponse(
        generated_sql=recommended["sql"],
        explanation=recommended["explanation"],
        queries=queries,
        recommended_index=parsed["recommended_index"],
        assumptions=parsed["assumptions"],
        dialect=request.dialect,
        validation=validation,
        usage=usage,
        raw_llm_output=raw_text,
    )


async def stream_generate_sql(
    request: NL2SQLRequest,
    adapter: ProviderAdapter,
) -> AsyncIterator[StreamEvent | NL2SQLStreamFinal]:
    """Consume a provider text stream, then emit a single structured result.

    Does not forward token deltas to callers (avoids streaming partial JSON in the UI).
    On completion, yields NL2SQLStreamFinal with validation and ``raw_llm_output``.
    """
    chat_req = _build_chat_request(request)
    collected_text = ""
    usage_info: dict[str, int | None] = {}

    try:
        stream_candidate = cast(
            AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]],
            adapter.stream_chat(chat_req),
        )
        if inspect.isawaitable(stream_candidate):
            stream = await cast(Awaitable[AsyncIterator[StreamEvent]], stream_candidate)
        else:
            stream = cast(AsyncIterator[StreamEvent], stream_candidate)

        async for event in stream:
            if isinstance(event, StreamDelta):
                collected_text += event.text
            elif isinstance(event, StreamMeta):
                pass
            elif isinstance(event, StreamFinal):
                if event.response:
                    collected_text = event.response.output_text or collected_text
                    usage_info = {
                        "prompt_tokens": event.response.usage.prompt_tokens,
                        "completion_tokens": event.response.usage.completion_tokens,
                        "total_tokens": event.response.usage.total_tokens,
                    }
            elif isinstance(event, StreamError):
                yield event
                return
    except Exception as exc:
        yield StreamError(message=str(exc))
        return

    parsed = _parse_llm_response(collected_text, request.dialect)
    recommended = parsed["queries"][parsed["recommended_index"]]
    validation = _run_validation(recommended["sql"], request.dialect, request.sandbox_ddl)
    queries = [SQLQuery(**q) for q in parsed["queries"]]

    yield NL2SQLStreamFinal(
        generated_sql=recommended["sql"],
        explanation=recommended["explanation"],
        queries=queries,
        recommended_index=parsed["recommended_index"],
        assumptions=parsed["assumptions"],
        dialect=request.dialect,
        validation=validation,
        usage=usage_info,
        raw_llm_output=collected_text,
    )


def _build_chat_request(request: NL2SQLRequest) -> ChatRequest:
    system_prompt = build_system_prompt(
        dialect=request.dialect,
        custom_prompt=request.system_prompt,
    )

    messages: list[Message] = [Message(role="system", content=system_prompt)]

    for turn in request.conversation_history:
        messages.append(Message(role=turn.role, content=turn.content))

    messages.append(Message(role="user", content=request.natural_language))

    provider_options = dict(request.provider_options)
    if request.provider in RESPONSE_FORMAT_PROVIDERS:
        provider_options["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "nl2sql_response",
                "strict": True,
                "schema": NL2SQL_JSON_SCHEMA,
            },
        }

    return ChatRequest(
        provider=request.provider,
        model=request.model,
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        provider_options=provider_options,
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def _parse_llm_response(text: str, dialect: SQLDialect = SQLDialect.postgresql) -> dict[str, Any]:
    """Parse structured JSON from LLM output.

    Tries direct JSON parse first, then strips markdown fences.
    Falls back to a legacy single-query wrapper if JSON parsing fails entirely.
    """
    cleaned = text.strip()

    # Try direct JSON parse
    parsed = _try_json_parse(cleaned)
    if parsed is not None:
        return _normalize_parsed(parsed)

    # Try extracting from markdown fences
    fence_match = _JSON_FENCE_RE.search(cleaned)
    if fence_match:
        parsed = _try_json_parse(fence_match.group(1).strip())
        if parsed is not None:
            return _normalize_parsed(parsed)

    # Fallback: treat entire output as a single SQL statement (legacy behavior)
    logger.warning("NL2SQL: JSON parse failed, falling back to raw text extraction")
    return {
        "queries": [{"title": "Generated query", "sql": cleaned, "explanation": ""}],
        "recommended_index": 0,
        "assumptions": [],
    }


def _try_json_parse(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "queries" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _normalize_parsed(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure all expected fields exist and have valid values."""
    queries = data.get("queries", [])
    if not queries:
        queries = [{"title": "Generated query", "sql": "", "explanation": ""}]

    for q in queries:
        q.setdefault("title", "Query")
        q.setdefault("sql", "")
        q.setdefault("explanation", "")

    rec_idx = data.get("recommended_index", 0)
    if not isinstance(rec_idx, int) or rec_idx < 0 or rec_idx >= len(queries):
        rec_idx = 0

    assumptions = data.get("assumptions", [])
    if not isinstance(assumptions, list):
        assumptions = []

    return {
        "queries": queries,
        "recommended_index": rec_idx,
        "assumptions": [str(a) for a in assumptions],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _run_validation(
    sql: str,
    dialect: SQLDialect,
    sandbox_ddl: str | None,
) -> SQLValidationResult:
    if not sql.strip():
        return SQLValidationResult(
            is_valid=False,
            syntax_errors=["No SQL was generated"],
        )

    if sandbox_ddl:
        return validate_with_sandbox(sql, dialect, sandbox_ddl)
    return validate_syntax(sql, dialect)
