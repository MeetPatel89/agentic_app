"""Tool execution orchestrator.

Implements the agentic tool-calling loop:
1. Send messages + tool definitions to the LLM via an adapter.
2. If the LLM responds with tool_calls, execute each tool.
3. Append the assistant message and tool results, then re-call the LLM.
4. Repeat until the LLM returns a text response or the iteration limit is reached.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.adapters.base import ProviderAdapter
from app.agentic.tools import ToolRegistry
from app.schemas import (
    ChatRequest,
    Message,
    NormalizedChatResponse,
    UsageInfo,
)

logger = logging.getLogger("llm_router")

MAX_TOOL_ITERATIONS = 10


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, max_iterations: int = MAX_TOOL_ITERATIONS) -> None:
        self._registry = registry
        self._max_iterations = max_iterations

    async def execute_with_tools(
        self,
        adapter: ProviderAdapter,
        req: ChatRequest,
    ) -> NormalizedChatResponse:
        """Run the tool-calling loop until the LLM produces a final text response."""
        messages = list(req.messages)
        total_usage = UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        response: NormalizedChatResponse | None = None

        for i in range(self._max_iterations):
            current_req = req.model_copy(update={"messages": messages})
            response = await adapter.chat(current_req)

            _accumulate_usage(total_usage, response.usage)

            if not response.tool_calls:
                break

            logger.info(
                "Tool loop iteration %d: %d tool call(s)",
                i + 1,
                len(response.tool_calls),
            )

            # Append the assistant message that requested tool calls
            messages.append(Message(
                role="assistant",
                content=response.output_text or None,
                tool_calls=response.tool_calls,
            ))

            # Execute each tool and append the result
            for tc in response.tool_calls:
                result = await self._execute_single(tc.function.name, tc.function.arguments)
                messages.append(Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                ))

        if response is None:
            raise RuntimeError("Tool executor produced no response")

        response.usage = total_usage
        return response

    async def _execute_single(self, name: str, arguments_json: str) -> str:
        tool = self._registry.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            args: dict[str, Any] = json.loads(arguments_json)
            return await tool.execute(args)
        except Exception as exc:
            logger.exception("Tool '%s' raised an exception", name)
            return f"Error executing tool '{name}': {exc}"


def _accumulate_usage(total: UsageInfo, delta: UsageInfo) -> None:
    total.prompt_tokens = (total.prompt_tokens or 0) + (delta.prompt_tokens or 0)
    total.completion_tokens = (total.completion_tokens or 0) + (delta.completion_tokens or 0)
    total.total_tokens = (total.total_tokens or 0) + (delta.total_tokens or 0)
