"""Tests for tool calling: concrete tools, registry, executor, and API integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.agentic.tools import (
    CalculateTool,
    GenerateUuidTool,
    GetCurrentTimeTool,
    JsonFormatterTool,
    ToolRegistry,
    WordCountTool,
)
from app.schemas import (
    ChatRequest,
    Message,
    NormalizedChatResponse,
    ToolCall,
    ToolCallFunction,
    ToolDefinitionRequest,
    ToolFunctionDefinition,
    UsageInfo,
)
from app.services.tool_executor import ToolExecutor

# ── Concrete tool unit tests ───────────────────────────────────────────────


class TestGetCurrentTimeTool:
    async def test_returns_iso_format(self):
        tool = GetCurrentTimeTool()
        result = await tool.execute({})
        # Should be parseable as ISO datetime and contain "T"
        assert "T" in result
        assert "UTC" in result or "+00:00" in result

    async def test_as_request_schema(self):
        tool = GetCurrentTimeTool()
        schema = tool.as_request_schema()
        assert isinstance(schema, ToolDefinitionRequest)
        assert schema.function.name == "get_current_time"


class TestCalculateTool:
    async def test_basic_addition(self):
        tool = CalculateTool()
        result = await tool.execute({"expression": "2 + 3"})
        assert result == "5"

    async def test_complex_expression(self):
        tool = CalculateTool()
        result = await tool.execute({"expression": "(10 + 5) * 2"})
        assert result == "30"

    async def test_float_division(self):
        tool = CalculateTool()
        result = await tool.execute({"expression": "7 / 2"})
        assert result == "3.5"

    async def test_floor_division(self):
        tool = CalculateTool()
        result = await tool.execute({"expression": "7 // 2"})
        assert result == "3"

    async def test_power(self):
        tool = CalculateTool()
        result = await tool.execute({"expression": "2 ** 10"})
        assert result == "1024"

    async def test_negative_number(self):
        tool = CalculateTool()
        result = await tool.execute({"expression": "-5 + 3"})
        assert result == "-2"

    async def test_rejects_function_call(self):
        tool = CalculateTool()
        with pytest.raises(ValueError, match="Unsupported"):
            await tool.execute({"expression": "len('abc')"})

    async def test_rejects_import(self):
        tool = CalculateTool()
        with pytest.raises(SyntaxError):
            await tool.execute({"expression": "import os"})

    async def test_division_by_zero(self):
        tool = CalculateTool()
        with pytest.raises(ZeroDivisionError):
            await tool.execute({"expression": "1 / 0"})


# ── Registry tests ─────────────────────────────────────────────────────────


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = GetCurrentTimeTool()
        registry.register(tool)
        assert registry.get("get_current_time") is tool

    def test_get_unknown_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_list_definitions(self):
        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        registry.register(CalculateTool())
        defs = registry.list_definitions()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"get_current_time", "calculate"}

    def test_list_request_schemas(self):
        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        schemas = registry.list_request_schemas()
        assert len(schemas) == 1
        assert schemas[0].type == "function"
        assert schemas[0].function.name == "get_current_time"


# ── ToolExecutor tests ─────────────────────────────────────────────────────


def _make_req(tools: list[ToolDefinitionRequest] | None = None) -> ChatRequest:
    return ChatRequest(
        provider="openai",
        model="gpt-4o",
        messages=[Message(role="user", content="hello")],
        tools=tools,
    )


def _make_tool_defs() -> list[ToolDefinitionRequest]:
    return [
        ToolDefinitionRequest(
            function=ToolFunctionDefinition(
                name="get_current_time",
                description="Returns the current time.",
                parameters={"type": "object", "properties": {}, "required": []},
            )
        ),
    ]


def _text_response(text: str = "Final answer") -> NormalizedChatResponse:
    return NormalizedChatResponse(
        output_text=text,
        finish_reason="stop",
        usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _tool_call_response(
    tool_name: str = "get_current_time",
    arguments: str = "{}",
    call_id: str = "call_1",
) -> NormalizedChatResponse:
    return NormalizedChatResponse(
        output_text="",
        finish_reason="tool_calls",
        tool_calls=[
            ToolCall(
                id=call_id,
                function=ToolCallFunction(name=tool_name, arguments=arguments),
            )
        ],
        usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class TestToolExecutor:
    async def test_no_tool_calls_passes_through(self):
        """When the LLM returns text directly, no tool loop happens."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        adapter = AsyncMock()
        adapter.chat = AsyncMock(return_value=_text_response("Hello!"))

        req = _make_req(tools=_make_tool_defs())
        result = await executor.execute_with_tools(adapter, req)

        assert result.output_text == "Hello!"
        adapter.chat.assert_called_once()

    async def test_single_tool_call_loop(self):
        """LLM calls a tool on the first turn, then responds with text."""
        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        executor = ToolExecutor(registry)

        adapter = AsyncMock()
        adapter.chat = AsyncMock(
            side_effect=[_tool_call_response(), _text_response("The time is 12:00")]
        )

        req = _make_req(tools=_make_tool_defs())
        result = await executor.execute_with_tools(adapter, req)

        assert result.output_text == "The time is 12:00"
        assert adapter.chat.call_count == 2

        # Verify the second call includes the tool result messages
        second_call_req = adapter.chat.call_args_list[1][0][0]
        roles = [m.role for m in second_call_req.messages]
        assert roles == ["user", "assistant", "tool"]

    async def test_unknown_tool_returns_error_string(self):
        """When the LLM requests an unknown tool, an error string is fed back."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        adapter = AsyncMock()
        adapter.chat = AsyncMock(
            side_effect=[
                _tool_call_response(tool_name="nonexistent"),
                _text_response("Sorry"),
            ]
        )

        req = _make_req(tools=_make_tool_defs())
        await executor.execute_with_tools(adapter, req)

        # Verify the tool result was an error message
        second_call_req = adapter.chat.call_args_list[1][0][0]
        tool_msg = [m for m in second_call_req.messages if m.role == "tool"][0]
        assert "Error: unknown tool 'nonexistent'" in tool_msg.content

    async def test_tool_exception_returns_error(self):
        """When a tool raises, the error is caught and fed back as a result."""
        registry = ToolRegistry()
        registry.register(CalculateTool())
        executor = ToolExecutor(registry)

        adapter = AsyncMock()
        adapter.chat = AsyncMock(
            side_effect=[
                _tool_call_response(
                    tool_name="calculate",
                    arguments=json.dumps({"expression": "1/0"}),
                ),
                _text_response("Cannot divide by zero"),
            ]
        )

        req = _make_req(tools=_make_tool_defs())
        await executor.execute_with_tools(adapter, req)

        second_call_req = adapter.chat.call_args_list[1][0][0]
        tool_msg = [m for m in second_call_req.messages if m.role == "tool"][0]
        assert "Error executing tool" in tool_msg.content

    async def test_max_iterations_safety(self):
        """Loop terminates after max_iterations even if the LLM keeps calling tools."""
        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        executor = ToolExecutor(registry, max_iterations=3)

        adapter = AsyncMock()
        # Always returns tool calls, never stops
        adapter.chat = AsyncMock(return_value=_tool_call_response())

        req = _make_req(tools=_make_tool_defs())
        await executor.execute_with_tools(adapter, req)

        assert adapter.chat.call_count == 3

    async def test_usage_aggregation(self):
        """Token usage is summed across all iterations."""
        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        executor = ToolExecutor(registry)

        adapter = AsyncMock()
        adapter.chat = AsyncMock(
            side_effect=[
                _tool_call_response(),  # usage: 10+5=15
                _text_response(),  # usage: 10+5=15
            ]
        )

        req = _make_req(tools=_make_tool_defs())
        result = await executor.execute_with_tools(adapter, req)

        assert result.usage.prompt_tokens == 20
        assert result.usage.completion_tokens == 10
        assert result.usage.total_tokens == 30

    async def test_multiple_parallel_tool_calls(self):
        """LLM requests two tool calls in one response."""
        registry = ToolRegistry()
        registry.register(GetCurrentTimeTool())
        registry.register(CalculateTool())
        executor = ToolExecutor(registry)

        multi_tool_response = NormalizedChatResponse(
            output_text="",
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    function=ToolCallFunction(name="get_current_time", arguments="{}"),
                ),
                ToolCall(
                    id="call_2",
                    function=ToolCallFunction(
                        name="calculate",
                        arguments=json.dumps({"expression": "2+2"}),
                    ),
                ),
            ],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        adapter = AsyncMock()
        adapter.chat = AsyncMock(
            side_effect=[multi_tool_response, _text_response("Done")]
        )

        req = _make_req(tools=_make_tool_defs())
        await executor.execute_with_tools(adapter, req)

        # Second call should have 2 tool result messages
        second_call_req = adapter.chat.call_args_list[1][0][0]
        tool_msgs = [m for m in second_call_req.messages if m.role == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0].tool_call_id == "call_1"
        assert tool_msgs[1].tool_call_id == "call_2"
        assert tool_msgs[1].content == "4"


# ── API integration tests ─────────────────────────────────────────────────


class TestChatAPIToolIntegration:
    async def test_chat_request_backward_compatible(self, client):
        """POST /api/chat without tools field still works."""
        resp = await client.post(
            "/api/chat",
            json={
                "provider": "nonexistent",
                "model": "test",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        # Should fail because provider doesn't exist, not because of schema
        assert resp.status_code == 400
        assert "not available" in resp.json()["detail"]

    async def test_chat_stream_with_tools_returns_400(self, client):
        """POST /api/chat/stream with tools returns 400."""
        resp = await client.post(
            "/api/chat/stream",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "description": "A test tool",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            },
        )
        assert resp.status_code == 400
        assert "not supported with streaming" in resp.json()["detail"]


# ── New tool unit tests ──────────────────────────────────────────────────


class TestGenerateUuidTool:
    async def test_returns_valid_uuid(self):
        import uuid

        tool = GenerateUuidTool()
        result = await tool.execute({})
        parsed = uuid.UUID(result)
        assert parsed.version == 4

    async def test_two_calls_differ(self):
        tool = GenerateUuidTool()
        a = await tool.execute({})
        b = await tool.execute({})
        assert a != b


class TestWordCountTool:
    async def test_known_text(self):
        tool = WordCountTool()
        result = json.loads(await tool.execute({"text": "Hello world. How are you?"}))
        assert result["words"] == 5
        assert result["characters"] == 25
        assert result["sentences"] == 2
        assert result["lines"] == 1

    async def test_empty_string(self):
        tool = WordCountTool()
        result = json.loads(await tool.execute({"text": ""}))
        assert result["words"] == 0
        assert result["characters"] == 0
        assert result["sentences"] == 0
        assert result["lines"] == 0

    async def test_multiline(self):
        tool = WordCountTool()
        result = json.loads(await tool.execute({"text": "Line one.\nLine two.\nLine three."}))
        assert result["words"] == 6
        assert result["lines"] == 3
        assert result["sentences"] == 3


class TestJsonFormatterTool:
    async def test_pretty_mode(self):
        tool = JsonFormatterTool()
        result = await tool.execute(
            {"json_string": '{"a":1,"b":2}', "mode": "pretty"}
        )
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}
        assert "\n" in result  # pretty-printed has newlines

    async def test_minify_mode(self):
        tool = JsonFormatterTool()
        result = await tool.execute(
            {"json_string": '{"a": 1, "b": 2}', "mode": "minify"}
        )
        assert result == '{"a":1,"b":2}'

    async def test_validate_mode_valid(self):
        tool = JsonFormatterTool()
        result = json.loads(
            await tool.execute({"json_string": '{"ok": true}', "mode": "validate"})
        )
        assert result["valid"] is True

    async def test_validate_mode_invalid(self):
        tool = JsonFormatterTool()
        result = json.loads(
            await tool.execute({"json_string": "{bad json", "mode": "validate"})
        )
        assert result["valid"] is False
        assert "error" in result


# ── Tool discovery endpoint tests ────────────────────────────────────────


class TestToolDiscoveryEndpoint:
    async def test_list_tools_returns_registered_tools(self, client):
        resp = await client.get("/api/tools")
        assert resp.status_code == 200
        data = resp.json()
        names = {t["name"] for t in data["tools"]}
        assert "get_current_time" in names
        assert "calculate" in names
        assert "generate_uuid" in names
        assert "word_count" in names
        assert "json_formatter" in names
        assert len(data["tools"]) == 5

    async def test_list_tools_schema_shape(self, client):
        resp = await client.get("/api/tools")
        data = resp.json()
        for tool in data["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "parameters_schema" in tool


# ── Turn-based tool integration tests ────────────────────────────────────


class TestTurnToolIntegration:
    async def test_unknown_tool_name_returns_400(self, client):
        resp = await client.post(
            "/api/chat/turn",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "message": "hi",
                "tool_mode": "manual",
                "tool_names": ["nonexistent_tool"],
            },
        )
        assert resp.status_code == 400
        assert "Unknown tool" in resp.json()["detail"]

    async def test_turn_stream_with_tools_returns_400(self, client):
        resp = await client.post(
            "/api/chat/turn/stream",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "message": "hi",
                "tool_mode": "manual",
                "tool_names": ["calculate"],
            },
        )
        assert resp.status_code == 400
        assert "not supported with streaming" in resp.json()["detail"]

    async def test_turn_without_tool_names_backward_compat(self, client):
        """Omitting tool_names still works (fails on provider, not schema)."""
        resp = await client.post(
            "/api/chat/turn",
            json={
                "provider": "nonexistent",
                "model": "test",
                "message": "hi",
            },
        )
        assert resp.status_code == 400
        assert "not available" in resp.json()["detail"]


# ── Tool mode tests ──────────────────────────────────────────────────────


class TestToolMode:
    async def test_auto_mode_injects_all_tools(self, client, monkeypatch):
        """tool_mode='auto' injects all 5 registered tools into ChatRequest."""
        from app.routers import chat as chat_module

        async def fake_prepare(db, req):
            if hasattr(chat_module._prepare_turn, '__wrapped__'):
                conv, chat_req, adapter, trace, parent_run_id = (
                    await chat_module._prepare_turn.__wrapped__(db, req)
                )
            else:
                _ = (None, None, None, None, None)
            # We can't easily intercept _prepare_turn, so test via the endpoint
            raise AssertionError("should not reach here in this test approach")

        # Instead, test by hitting the endpoint and checking what _prepare_turn builds
        # We mock the adapter to capture the chat_req
        from unittest.mock import AsyncMock, patch

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=NormalizedChatResponse(
            output_text="It is 12:00",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))

        with patch("app.routers.chat.get_adapter", return_value=mock_adapter):
            resp = await client.post(
                "/api/chat/turn",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "message": "What time is it?",
                    "tool_mode": "auto",
                },
            )

        assert resp.status_code == 200
        # Verify the adapter received tools in the request
        call_args = mock_adapter.chat.call_args[0][0]
        assert call_args.tools is not None
        assert len(call_args.tools) == 5
        assert call_args.tool_choice == "auto"
        tool_names = {t.function.name for t in call_args.tools}
        assert "get_current_time" in tool_names
        assert "calculate" in tool_names
        assert "generate_uuid" in tool_names
        assert "word_count" in tool_names
        assert "json_formatter" in tool_names

    async def test_off_mode_sends_no_tools(self, client, monkeypatch):
        """tool_mode='off' (default) sends no tools."""
        from unittest.mock import AsyncMock, patch

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=NormalizedChatResponse(
            output_text="I cannot check the time.",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))

        with patch("app.routers.chat.get_adapter", return_value=mock_adapter):
            resp = await client.post(
                "/api/chat/turn",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "message": "What time is it?",
                    "tool_mode": "off",
                },
            )

        assert resp.status_code == 200
        call_args = mock_adapter.chat.call_args[0][0]
        assert call_args.tools is None
        assert call_args.tool_choice is None

    async def test_manual_mode_with_tool_names(self, client):
        """tool_mode='manual' with tool_names resolves named tools."""
        from unittest.mock import AsyncMock, patch

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=NormalizedChatResponse(
            output_text="2+2=4",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))

        with patch("app.routers.chat.get_adapter", return_value=mock_adapter):
            resp = await client.post(
                "/api/chat/turn",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "message": "Calculate 2+2",
                    "tool_mode": "manual",
                    "tool_names": ["calculate"],
                },
            )

        assert resp.status_code == 200
        call_args = mock_adapter.chat.call_args[0][0]
        assert call_args.tools is not None
        assert len(call_args.tools) == 1
        assert call_args.tools[0].function.name == "calculate"
        assert call_args.tool_choice == "auto"

    async def test_manual_mode_without_tool_names_sends_no_tools(self, client):
        """tool_mode='manual' without tool_names = no tools."""
        from unittest.mock import AsyncMock, patch

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=NormalizedChatResponse(
            output_text="Hello!",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))

        with patch("app.routers.chat.get_adapter", return_value=mock_adapter):
            resp = await client.post(
                "/api/chat/turn",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "message": "hi",
                    "tool_mode": "manual",
                },
            )

        assert resp.status_code == 200
        call_args = mock_adapter.chat.call_args[0][0]
        assert call_args.tools is None
        assert call_args.tool_choice is None

    async def test_streaming_with_auto_mode_returns_400(self, client):
        """Streaming + tool_mode='auto' returns 400."""
        resp = await client.post(
            "/api/chat/turn/stream",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "message": "hi",
                "tool_mode": "auto",
            },
        )
        assert resp.status_code == 400
        assert "not supported with streaming" in resp.json()["detail"]

    async def test_omitting_tool_mode_defaults_to_off(self, client):
        """Backward compatibility: omitting tool_mode defaults to 'off'."""
        from unittest.mock import AsyncMock, patch

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=NormalizedChatResponse(
            output_text="Hello!",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))

        with patch("app.routers.chat.get_adapter", return_value=mock_adapter):
            resp = await client.post(
                "/api/chat/turn",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "message": "hi",
                    # No tool_mode field at all
                },
            )

        assert resp.status_code == 200
        call_args = mock_adapter.chat.call_args[0][0]
        assert call_args.tools is None
        assert call_args.tool_choice is None

    async def test_streaming_with_manual_tools_returns_400(self, client):
        """Streaming + tool_mode='manual' with tool_names returns 400."""
        resp = await client.post(
            "/api/chat/turn/stream",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "message": "hi",
                "tool_mode": "manual",
                "tool_names": ["calculate"],
            },
        )
        assert resp.status_code == 400
        assert "not supported with streaming" in resp.json()["detail"]

    async def test_streaming_with_off_mode_allowed(self, client):
        """Streaming + tool_mode='off' should not be blocked."""
        from unittest.mock import AsyncMock, patch

        mock_adapter = AsyncMock()

        async def fake_stream(req):
            from app.schemas import StreamFinal
            yield StreamFinal(response=NormalizedChatResponse(
                output_text="Hi!",
                finish_reason="stop",
                usage=UsageInfo(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            ))

        mock_adapter.stream_chat = fake_stream

        with patch("app.routers.chat.get_adapter", return_value=mock_adapter):
            resp = await client.post(
                "/api/chat/turn/stream",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "message": "hi",
                    "tool_mode": "off",
                },
            )

        assert resp.status_code == 200
