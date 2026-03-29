from __future__ import annotations

from collections.abc import AsyncIterator

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import ChatRequest, NormalizedChatResponse, StreamError


class AzureOpenAIAdapter(ProviderAdapter):
    """Scaffold for Azure OpenAI. Requires openai SDK with azure config."""

    name = "azure_openai"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.azure_openai_api_key
        self._endpoint = settings.azure_openai_endpoint
        self._api_version = settings.azure_openai_api_version

    def is_available(self) -> bool:
        return bool(self._api_key and self._endpoint)

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        # TODO: Implement using openai.AsyncAzureOpenAI
        raise NotImplementedError("Azure OpenAI adapter not yet implemented")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamError(message="Azure OpenAI streaming not yet implemented")
