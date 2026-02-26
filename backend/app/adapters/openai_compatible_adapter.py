from __future__ import annotations

from typing import AsyncIterator

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
    UsageInfo,
)


class OpenAICompatibleAdapter(ProviderAdapter):
    """Adapter for local / open-source models exposed via an OpenAI-compatible API
    (vLLM, Ollama, LM Studio, etc.)."""

    name = "local_openai_compatible"

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.local_openai_base_url
        self._api_key = settings.local_openai_api_key
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._base_url)

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
            max_tokens=req.max_tokens,
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
                max_tokens=req.max_tokens,
                stream=True,
                **req.provider_options,
            )
            yield StreamMeta(provider=self.name, model=req.model)

            full_text = ""
            finish_reason = None
            resp_id = None

            async for chunk in stream:
                resp_id = chunk.id
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_text += delta.content
                        yield StreamDelta(text=delta.content)
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason

            yield StreamFinal(
                response=NormalizedChatResponse(
                    output_text=full_text,
                    finish_reason=finish_reason,
                    provider_response_id=resp_id,
                    usage=UsageInfo(),
                    raw={},
                )
            )
        except Exception as exc:
            yield StreamError(message=str(exc))
