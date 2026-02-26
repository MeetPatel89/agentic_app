"""Stub: Pluggable memory stores for agentic workflows (v2+).

Design:
- MemoryStore interface lets agents persist and retrieve context across turns.
- Implementations could be in-memory, SQLite, Redis, vector DB, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryStore(ABC):
    @abstractmethod
    async def store(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        ...

    @abstractmethod
    async def retrieve(self, key: str) -> Any | None:
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[Any]:
        ...

    @abstractmethod
    async def clear(self) -> None:
        ...


class InMemoryStore(MemoryStore):
    """Simple in-memory implementation for local dev / testing."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def store(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        self._data[key] = value

    async def retrieve(self, key: str) -> Any | None:
        return self._data.get(key)

    async def search(self, query: str, top_k: int = 5) -> list[Any]:
        # Naive substring match for stub
        return [v for k, v in self._data.items() if query.lower() in str(k).lower()][:top_k]

    async def clear(self) -> None:
        self._data.clear()
