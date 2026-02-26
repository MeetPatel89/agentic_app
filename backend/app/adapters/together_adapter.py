from __future__ import annotations

from typing import AsyncIterator

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import ChatRequest, NormalizedChatResponse, StreamError


class TogetherAdapter(ProviderAdapter):
    """Scaffold for Together AI. Uses OpenAI-compatible API."""

    name = "together"

    def __init__(self) -> None:
        self._api_key = get_settings().together_api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        # TODO: Implement using OpenAI client with Together's base_url
        raise NotImplementedError("Together adapter not yet implemented")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamError(message="Together streaming not yet implemented")
