from __future__ import annotations

from collections.abc import AsyncIterator

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import ChatRequest, NormalizedChatResponse, StreamError


class GroqAdapter(ProviderAdapter):
    """Scaffold for Groq. Uses OpenAI-compatible API under the hood."""

    name = "groq"

    def __init__(self) -> None:
        self._api_key = get_settings().groq_api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        # TODO: Implement using groq SDK or OpenAI client with base_url
        raise NotImplementedError("Groq adapter not yet implemented")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamError(message="Groq streaming not yet implemented")
