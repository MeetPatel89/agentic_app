"""Stub: Tool calling & registry for agentic workflows (v2+).

Design:
- Tools are registered with a name, description, and JSON schema for parameters.
- The LLM adapter can include tool definitions in the request.
- When the LLM returns a tool_call, the orchestrator invokes the tool and feeds the
  result back as a tool-role message in a follow-up turn.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: dict[str, Any]


class Tool(ABC):
    definition: ToolDefinition

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """Run the tool and return a string result."""
        ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]


# Singleton for the app
tool_registry = ToolRegistry()
