from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from app.adapters.base import ProviderAdapter, StreamEvent
from app.nl2sql.prompts import build_system_prompt
from app.nl2sql.sandbox import validate_syntax, validate_with_sandbox
from app.nl2sql.schemas import (
    NL2SQLRequest,
    NL2SQLResponse,
    NL2SQLStreamFinal,
    SQLDialect,
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
    generated_sql, explanation = _extract_sql_and_explanation(raw_text)

    validation = _run_validation(generated_sql, request.dialect, request.sandbox_ddl)

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }

    return NL2SQLResponse(
        generated_sql=generated_sql,
        explanation=explanation,
        dialect=request.dialect,
        validation=validation,
        usage=usage,
    )


async def stream_generate_sql(
    request: NL2SQLRequest,
    adapter: ProviderAdapter,
) -> AsyncIterator[StreamEvent | NL2SQLStreamFinal]:
    """Stream SQL generation, then validate on completion.

    Yields standard StreamDelta/StreamMeta events during generation.
    On completion, yields an NL2SQLStreamFinal (instead of the regular StreamFinal)
    that includes validation results.
    """
    chat_req = _build_chat_request(request)
    collected_text = ""
    usage_info: dict[str, int | None] = {}

    try:
        async for event in adapter.stream_chat(chat_req):
            if isinstance(event, StreamDelta):
                collected_text += event.text
                yield event
            elif isinstance(event, StreamMeta):
                yield event
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

    generated_sql, explanation = _extract_sql_and_explanation(collected_text)
    validation = _run_validation(generated_sql, request.dialect, request.sandbox_ddl)

    yield NL2SQLStreamFinal(
        generated_sql=generated_sql,
        explanation=explanation,
        dialect=request.dialect,
        validation=validation,
        usage=usage_info,
    )


def _build_chat_request(request: NL2SQLRequest) -> ChatRequest:
    system_prompt = build_system_prompt(
        dialect=request.dialect,
        custom_prompt=request.system_prompt,
    )

    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=request.natural_language),
    ]

    return ChatRequest(
        provider=request.provider,
        model=request.model,
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        provider_options=request.provider_options,
    )


_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_EXPLANATION_RE = re.compile(r"--\s*Explanation:\s*(.*)", re.DOTALL)


def _extract_sql_and_explanation(text: str) -> tuple[str, str]:
    """Extract SQL and explanation from LLM output.

    Handles both fenced code blocks and raw SQL output.
    """
    fence_match = _SQL_FENCE_RE.search(text)
    if fence_match:
        sql_block = fence_match.group(1).strip()
        remainder = text[fence_match.end():].strip()
    else:
        sql_block = text.strip()
        remainder = ""

    explanation_match = _EXPLANATION_RE.search(sql_block)
    if explanation_match:
        explanation = explanation_match.group(1).strip()
        sql_block = sql_block[: explanation_match.start()].strip()
    elif remainder:
        explanation_match = _EXPLANATION_RE.search(remainder)
        if explanation_match:
            explanation = explanation_match.group(1).strip()
        else:
            explanation = remainder
    else:
        explanation = ""

    return sql_block, explanation


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
