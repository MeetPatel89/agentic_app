from __future__ import annotations

from typing import AsyncIterator

import anthropic

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import (
    ChatRequest,
    NormalizedChatResponse,
    StreamDelta,
    StreamError,
    StreamFinal,
    StreamMeta,
    UsageInfo,
)


class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.anthropic_api_key
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _split_system(self, req: ChatRequest) -> tuple[str | anthropic.NotGiven, list[dict]]:
        system_text = anthropic.NOT_GIVEN
        messages: list[dict] = []
        for m in req.messages:
            if m.role == "system":
                system_text = m.content
            else:
                messages.append({"role": m.role, "content": m.content})
        return system_text, messages

    async def list_models(self) -> list[str]:
        client = self._get_client()
        models: list[str] = []
        async for model in client.models.list(limit=1000):
            model_id = getattr(model, "id", None)
            if model_id:
                models.append(model_id)
        return sorted(set(models))

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        client = self._get_client()
        system, messages = self._split_system(req)
        resp = await client.messages.create(
            model=req.model,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            **req.provider_options,
        )
        text_parts = [block.text for block in resp.content if block.type == "text"]
        raw = resp.model_dump()
        return NormalizedChatResponse(
            output_text="".join(text_parts),
            finish_reason=resp.stop_reason,
            provider_response_id=resp.id,
            usage=UsageInfo(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
                total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            ),
            raw=raw,
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        system, messages = self._split_system(req)
        try:
            yield StreamMeta(provider=self.name, model=req.model)
            full_text = ""
            resp_id: str | None = None
            finish_reason: str | None = None
            usage_info = UsageInfo()

            async with client.messages.stream(
                model=req.model,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                **req.provider_options,
            ) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        resp_id = event.message.id
                        usage_info.prompt_tokens = event.message.usage.input_tokens
                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            full_text += event.delta.text
                            yield StreamDelta(text=event.delta.text)
                    elif event.type == "message_delta":
                        finish_reason = event.delta.stop_reason  # type: ignore[union-attr]
                        if hasattr(event, "usage") and event.usage:
                            usage_info.completion_tokens = event.usage.output_tokens
                            usage_info.total_tokens = (usage_info.prompt_tokens or 0) + event.usage.output_tokens

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
