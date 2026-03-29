from __future__ import annotations

from collections.abc import AsyncIterator

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import ChatRequest, NormalizedChatResponse, StreamError


class MistralAdapter(ProviderAdapter):
    """Scaffold for Mistral AI. Requires mistralai SDK."""

    name = "mistral"

    def __init__(self) -> None:
        self._api_key = get_settings().mistral_api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        # TODO: Implement using mistralai SDK
        raise NotImplementedError("Mistral adapter not yet implemented")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamError(message="Mistral streaming not yet implemented")
