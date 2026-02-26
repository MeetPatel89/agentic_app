from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.adapters.anthropic_adapter import AnthropicAdapter
from app.adapters.azure_openai_adapter import AzureOpenAIAdapter
from app.adapters.google_adapter import GoogleGeminiAdapter
from app.adapters.groq_adapter import GroqAdapter
from app.adapters.mistral_adapter import MistralAdapter
from app.adapters.openai_adapter import OpenAIAdapter
from app.adapters.openai_compatible_adapter import OpenAICompatibleAdapter
from app.adapters.together_adapter import TogetherAdapter

if TYPE_CHECKING:
    from app.adapters.base import ProviderAdapter

logger = logging.getLogger(__name__)

_ALL_ADAPTERS: list[type[ProviderAdapter]] = [
    OpenAIAdapter,
    AnthropicAdapter,
    OpenAICompatibleAdapter,
    GoogleGeminiAdapter,
    MistralAdapter,
    GroqAdapter,
    TogetherAdapter,
    AzureOpenAIAdapter,
]

_registry: dict[str, ProviderAdapter] = {}


def init_registry() -> None:
    """Instantiate all adapters, register those whose credentials are present."""
    _registry.clear()
    for cls in _ALL_ADAPTERS:
        adapter = cls()
        if adapter.is_available():
            _registry[adapter.name] = adapter
            logger.info("Provider registered: %s", adapter.name)
        else:
            logger.info("Provider skipped (no credentials): %s", adapter.name)


def get_adapter(name: str) -> ProviderAdapter | None:
    return _registry.get(name)


def list_providers() -> list[str]:
    return list(_registry.keys())


def all_provider_names() -> list[str]:
    """All known provider names regardless of availability."""
    return [cls.name for cls in _ALL_ADAPTERS if hasattr(cls, "name")]
