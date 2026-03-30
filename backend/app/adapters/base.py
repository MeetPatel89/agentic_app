from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas import ChatRequest, NormalizedChatResponse, StreamDelta, StreamError, StreamFinal, StreamMeta

StreamEvent = StreamDelta | StreamMeta | StreamFinal | StreamError


class ProviderAdapter(ABC):
    """Base class all provider adapters must implement."""

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider's credentials / config are present."""
        ...

    @abstractmethod
    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        """Synchronous (non-streaming) chat completion."""
        ...

    @abstractmethod
    def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Yield streaming events: delta, meta, final, or error."""
        ...

    async def list_models(self) -> list[str]:
        """Return provider model IDs available to the configured account."""
        return []
