from __future__ import annotations

from typing import AsyncIterator

from app.adapters.base import ProviderAdapter, StreamEvent
from app.config import get_settings
from app.schemas import ChatRequest, NormalizedChatResponse, StreamError


class GoogleGeminiAdapter(ProviderAdapter):
    """Scaffold for Google Gemini. Requires google-generativeai SDK."""

    name = "google_gemini"

    def __init__(self) -> None:
        self._api_key = get_settings().google_api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        # TODO: Implement using google-generativeai SDK
        raise NotImplementedError("Google Gemini adapter not yet implemented")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield StreamError(message="Google Gemini streaming not yet implemented")
