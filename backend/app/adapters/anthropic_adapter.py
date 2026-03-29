from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

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
    ToolCall,
    ToolCallFunction,
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

    # ── Message conversion ────────────────────────────────────────────────

    def _build_messages(self, req: ChatRequest) -> tuple[str | None, list[dict[str, Any]]]:
        """Split system prompt and convert messages to Anthropic format.

        Handles tool-loop messages:
        - assistant messages with tool_calls → content blocks with text + tool_use
        - tool role messages → user messages with tool_result content blocks
        """
        system_text: str | None = None
        messages: list[dict[str, Any]] = []

        i = 0
        msg_list = req.messages
        while i < len(msg_list):
            m = msg_list[i]

            if m.role == "system":
                system_text = m.content
                i += 1
                continue

            if m.role == "assistant" and m.tool_calls:
                # Build content blocks: optional text + tool_use blocks
                content: list[dict[str, Any]] = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments),
                    })
                messages.append({"role": "assistant", "content": content})
                i += 1
                continue

            if m.role == "tool":
                # Collect consecutive tool-result messages into one user message
                tool_results: list[dict[str, Any]] = []
                while i < len(msg_list) and msg_list[i].role == "tool":
                    tm = msg_list[i]
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tm.tool_call_id,
                        "content": tm.content or "",
                    })
                    i += 1
                messages.append({"role": "user", "content": tool_results})
                continue

            # Regular user/assistant message
            messages.append({"role": m.role, "content": m.content or ""})
            i += 1

        return system_text, messages

    # ── Tool definition conversion ────────────────────────────────────────

    def _build_tool_kwargs(self, req: ChatRequest) -> dict[str, Any]:
        """Convert OpenAI-format tool definitions to Anthropic format."""
        kwargs: dict[str, Any] = {}
        if req.tools:
            kwargs["tools"] = [
                {
                    "name": t.function.name,
                    "description": t.function.description,
                    "input_schema": t.function.parameters,
                }
                for t in req.tools
            ]
        if req.tool_choice:
            kwargs["tool_choice"] = self._convert_tool_choice(req.tool_choice)
        return kwargs

    @staticmethod
    def _convert_tool_choice(choice: str) -> dict[str, str]:
        """Map OpenAI tool_choice strings to Anthropic's format."""
        mapping = {
            "auto": {"type": "auto"},
            "none": {"type": "none"},      # Anthropic: don't use tools
            "required": {"type": "any"},   # Anthropic: must use a tool
        }
        return mapping.get(choice, {"type": "auto"})

    # ── Response parsing ──────────────────────────────────────────────────

    @staticmethod
    def _parse_response(resp: anthropic.types.Message) -> NormalizedChatResponse:
        """Extract text and tool_calls from an Anthropic response."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    type="function",
                    function=ToolCallFunction(
                        name=block.name,
                        arguments=json.dumps(block.input),
                    ),
                ))

        return NormalizedChatResponse(
            output_text="".join(text_parts),
            finish_reason=resp.stop_reason,
            provider_response_id=resp.id,
            usage=UsageInfo(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
                total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            ),
            tool_calls=tool_calls or None,
            raw=resp.model_dump(),
        )

    # ── Public API ────────────────────────────────────────────────────────

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
        system, messages = self._build_messages(req)

        create_kwargs: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
            "temperature": req.temperature if req.temperature is not None else 0.7,
            "max_tokens": req.max_tokens,
            **self._build_tool_kwargs(req),
            **req.provider_options,
        }
        if system:
            create_kwargs["system"] = system

        resp = await client.messages.create(**create_kwargs)
        return self._parse_response(resp)

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        system, messages = self._build_messages(req)

        stream_kwargs: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            **self._build_tool_kwargs(req),
            **req.provider_options,
        }
        if system:
            stream_kwargs["system"] = system

        try:
            yield StreamMeta(provider=self.name, model=req.model)
            full_text = ""
            resp_id: str | None = None
            finish_reason: str | None = None
            usage_info = UsageInfo()

            async with client.messages.stream(**stream_kwargs) as stream:
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
