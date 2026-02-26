from __future__ import annotations

import json
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import (
    ChatRequest,
    NormalizedChatResponse,
    StreamDelta,
    StreamFinal,
    StreamMeta,
    StreamError,
    UsageInfo,
)


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

    def _build_messages(self, req: ChatRequest) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in req.messages]

    async def list_models(self) -> list[str]:
        client = self._get_client()
        models: list[str] = []
        async for model in client.models.list():
            model_id = getattr(model, "id", None)
            if model_id:
                models.append(model_id)
        return sorted(set(models))

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=req.model,
            messages=self._build_messages(req),  # type: ignore[arg-type]
            temperature=req.temperature,
            max_completion_tokens=req.max_tokens,
            **req.provider_options,
        )
        choice = resp.choices[0]
        usage = resp.usage
        raw = resp.model_dump()
        return NormalizedChatResponse(
            output_text=choice.message.content or "",
            finish_reason=choice.finish_reason,
            provider_response_id=resp.id,
            usage=UsageInfo(
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
            ),
            raw=raw,
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        try:
            stream = await client.chat.completions.create(
                model=req.model,
                messages=self._build_messages(req),  # type: ignore[arg-type]
                temperature=req.temperature,
                max_completion_tokens=req.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
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
