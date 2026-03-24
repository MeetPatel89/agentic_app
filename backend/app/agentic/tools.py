"""Tool calling & registry for agentic workflows.

Design:
- Tools are registered with a name, description, and JSON schema for parameters.
- The LLM adapter can include tool definitions in the request.
- When the LLM returns a tool_call, the orchestrator invokes the tool and feeds the
  result back as a tool-role message in a follow-up turn.
"""

from __future__ import annotations

import ast
import json
import operator
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.schemas import ToolDefinitionRequest, ToolFunctionDefinition


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

    def as_request_schema(self) -> ToolDefinitionRequest:
        """Convert to the wire format sent to LLM providers."""
        return ToolDefinitionRequest(
            function=ToolFunctionDefinition(
                name=self.definition.name,
                description=self.definition.description,
                parameters=self.definition.parameters_schema,
            )
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def list_request_schemas(self) -> list[ToolDefinitionRequest]:
        """Return all tool definitions in the wire format for LLM requests."""
        return [t.as_request_schema() for t in self._tools.values()]


# ── Concrete tools ─────────────────────────────────────────────────────────


class GetCurrentTimeTool(Tool):
    definition = ToolDefinition(
        name="get_current_time",
        description="Returns the current date and time in ISO 8601 format.",
        parameters_schema={"type": "object", "properties": {}, "required": []},
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        return datetime.now(UTC).isoformat()


# Safe math evaluator — walks the AST and only allows arithmetic operations.
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.expr) -> float | int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


class CalculateTool(Tool):
    definition = ToolDefinition(
        name="calculate",
        description="Evaluates a math expression. Supports +, -, *, /, //, %, **.",
        parameters_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression, e.g. '2 + 3 * 4'",
                }
            },
            "required": ["expression"],
        },
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        expression = arguments.get("expression", "")
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)


class GenerateUuidTool(Tool):
    definition = ToolDefinition(
        name="generate_uuid",
        description="Generates a random UUID v4. Useful when a unique identifier is needed.",
        parameters_schema={"type": "object", "properties": {}, "required": []},
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        return str(uuid.uuid4())


class WordCountTool(Tool):
    definition = ToolDefinition(
        name="word_count",
        description="Counts words, characters, sentences, and lines in the given text.",
        parameters_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to analyze.",
                }
            },
            "required": ["text"],
        },
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        import re

        text: str = arguments.get("text", "")
        words = len(text.split()) if text else 0
        characters = len(text)
        sentences = len(re.findall(r"[.!?]+(?:\s|$)", text)) if text else 0
        lines = len(text.splitlines()) if text else 0
        return json.dumps(
            {"words": words, "characters": characters, "sentences": sentences, "lines": lines}
        )


class JsonFormatterTool(Tool):
    definition = ToolDefinition(
        name="json_formatter",
        description="Validates, pretty-prints, or minifies a JSON string.",
        parameters_schema={
            "type": "object",
            "properties": {
                "json_string": {
                    "type": "string",
                    "description": "The JSON string to process.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["pretty", "minify", "validate"],
                    "description": (
                        "Operation mode: 'pretty' to format with indentation,"
                        " 'minify' to compact, 'validate' to check validity."
                    ),
                },
            },
            "required": ["json_string", "mode"],
        },
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        json_string: str = arguments.get("json_string", "")
        mode: str = arguments.get("mode", "validate")

        try:
            parsed = json.loads(json_string)
        except json.JSONDecodeError as exc:
            return json.dumps({"valid": False, "error": str(exc)})

        if mode == "pretty":
            return json.dumps(parsed, indent=2)
        elif mode == "minify":
            return json.dumps(parsed, separators=(",", ":"))
        else:  # validate
            return json.dumps({"valid": True})


# ── Registration ───────────────────────────────────────────────────────────

# Singleton for the app
tool_registry = ToolRegistry()


def register_default_tools() -> None:
    """Register the built-in tools. Called once at app startup."""
    tool_registry.register(GetCurrentTimeTool())
    tool_registry.register(CalculateTool())
    tool_registry.register(GenerateUuidTool())
    tool_registry.register(WordCountTool())
    tool_registry.register(JsonFormatterTool())
