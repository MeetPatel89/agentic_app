from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import (
    ChatRequest,
    NormalizedChatResponse,
    StreamDelta,
    StreamError,
    StreamFinal,
    StreamMeta,
    ToolCall,
    ToolCallFunction,
    UsageInfo,
)

# Reasoning models don't support sampling parameters like temperature.
# o-series: o1, o1-mini, o3, o3-mini, o3-pro, o4-mini, etc.
# gpt-5 family (gpt-5-mini, gpt-5.1, gpt-5.1-mini, etc.) are also reasoning models.
_REASONING_MODEL_RE = re.compile(r"^(o\d|gpt-5)", re.IGNORECASE)


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _build_messages(self, req: ChatRequest) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for m in req.messages:
            msg: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                msg["content"] = m.content
            if m.name is not None:
                msg["name"] = m.name
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                msg["tool_calls"] = [tc.model_dump() for tc in m.tool_calls]
            result.append(msg)
        print("--------------------------------")
        print("Messages: ", result)
        print("--------------------------------")
        return result

    def _build_tool_kwargs(self, req: ChatRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if req.tools:
            kwargs["tools"] = [t.model_dump() for t in req.tools]
        if req.tool_choice:
            kwargs["tool_choice"] = req.tool_choice
        return kwargs

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        return bool(_REASONING_MODEL_RE.match(model))

    async def list_models(self) -> list[str]:
        client = self._get_client()
        models: list[str] = []
        async for model in client.models.list():
            model_id = getattr(model, "id", None)
            if model_id:
                models.append(model_id)
        return sorted(set(models))

    def _build_sampling_kwargs(self, req: ChatRequest) -> dict[str, Any]:
        """Build sampling params, omitting temperature for reasoning models."""
        kwargs: dict[str, Any] = {}
        if req.temperature is not None and not self._is_reasoning_model(req.model):
            kwargs["temperature"] = req.temperature
        return kwargs

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        client = self._get_client()
        print("--------------------------------")
        print("From chat: ")
        print("Request: ", req)
        print("--------------------------------")
        resp = await client.chat.completions.create(
            model=req.model,
            messages=self._build_messages(req),  # type: ignore[arg-type]
            max_completion_tokens=req.max_tokens,
            **self._build_sampling_kwargs(req),
            **self._build_tool_kwargs(req),
            **req.provider_options,
        )
        print("--------------------------------")
        print("Response from chat: ", resp)
        print("--------------------------------")
        choice = resp.choices[0]
        usage = resp.usage
        raw = resp.model_dump()

        # Parse tool_calls from the assistant response
        normalized_tool_calls = None
        if choice.message.tool_calls:
            normalized_tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function=ToolCallFunction(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    ),
                )
                for tc in choice.message.tool_calls
            ]

        return NormalizedChatResponse(
            output_text=choice.message.content or "",
            finish_reason=choice.finish_reason,
            provider_response_id=resp.id,
            usage=UsageInfo(
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
            ),
            tool_calls=normalized_tool_calls,
            raw=raw,
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        print("--------------------------------")
        print("From stream_chat: ")
        print("Request: ", req)
        print("--------------------------------")
        try:
            stream = await client.chat.completions.create(
                model=req.model,
                messages=self._build_messages(req),  # type: ignore[arg-type]
                max_completion_tokens=req.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
                **self._build_sampling_kwargs(req),
                **req.provider_options,
            )
            yield StreamMeta(provider=self.name, model=req.model)

            full_text = ""
            finish_reason = None
            resp_id = None
            usage_info = UsageInfo()

            async for chunk in stream:
                resp_id = chunk.id
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_text += delta.content
                        yield StreamDelta(text=delta.content)
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                if chunk.usage:
                    usage_info = UsageInfo(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )

            yield StreamFinal(
                response=NormalizedChatResponse(
                    output_text=full_text,
                    finish_reason=finish_reason,
                    provider_response_id=resp_id,
                    usage=usage_info,
                    raw={},
                )
            )
        except Exception as exc:
            yield StreamError(message=str(exc))
