from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.adapters.base import ProviderAdapter
from app.nl2sql.schemas import NL2SQLHistoryMessage, NL2SQLRequest, SQLDialect
from app.nl2sql.service import _build_chat_request, _parse_llm_response, generate_sql, stream_generate_sql
from app.schemas import NormalizedChatResponse, StreamDelta, StreamFinal, UsageInfo


def _make_json_output(
    queries: list[dict],
    recommended_index: int = 0,
    assumptions: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "queries": queries,
            "recommended_index": recommended_index,
            "assumptions": assumptions or [],
        }
    )


def _make_mock_adapter(output_text: str) -> ProviderAdapter:
    adapter = AsyncMock(spec=ProviderAdapter)
    adapter.chat.return_value = NormalizedChatResponse(
        output_text=output_text,
        finish_reason="stop",
        usage=UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    return adapter


class TestParseLLMResponse:
    def test_single_query_json(self):
        text = _make_json_output(
            [
                {"title": "All users", "sql": "SELECT id FROM users;", "explanation": "Gets all user IDs"},
            ]
        )
        result = _parse_llm_response(text)
        assert len(result["queries"]) == 1
        assert result["queries"][0]["sql"] == "SELECT id FROM users;"
        assert result["queries"][0]["title"] == "All users"
        assert result["recommended_index"] == 0

    def test_multiple_queries_json(self):
        text = _make_json_output(
            [
                {
                    "title": "Simple top 10",
                    "sql": "SELECT * FROM emp ORDER BY salary DESC LIMIT 10",
                    "explanation": "No tie handling",
                },
                {
                    "title": "With ties",
                    "sql": (
                        "SELECT * FROM emp WHERE salary >= "
                        "(SELECT MIN(s) FROM (SELECT salary AS s FROM emp ORDER BY salary DESC LIMIT 10) t)"
                    ),
                    "explanation": "Includes tied employees",
                },
            ],
            recommended_index=1,
            assumptions=["Table 'emp' has a 'salary' column"],
        )
        result = _parse_llm_response(text)
        assert len(result["queries"]) == 2
        assert result["recommended_index"] == 1
        assert "salary" in result["assumptions"][0]

    def test_json_in_markdown_fence(self):
        inner = json.dumps(
            {
                "queries": [{"title": "Q", "sql": "SELECT 1", "explanation": ""}],
                "recommended_index": 0,
                "assumptions": [],
            }
        )
        text = f"```json\n{inner}\n```"
        result = _parse_llm_response(text)
        assert result["queries"][0]["sql"] == "SELECT 1"

    def test_fallback_raw_sql(self):
        text = "SELECT id FROM users WHERE active = true"
        result = _parse_llm_response(text)
        assert len(result["queries"]) == 1
        assert result["queries"][0]["sql"] == text
        assert result["queries"][0]["title"] == "Generated query"

    def test_invalid_json_falls_back(self):
        text = '{"queries": broken}'
        result = _parse_llm_response(text)
        assert len(result["queries"]) == 1
        assert result["queries"][0]["sql"] == text

    def test_missing_fields_normalized(self):
        text = json.dumps({"queries": [{"sql": "SELECT 1"}], "recommended_index": 0})
        result = _parse_llm_response(text)
        assert result["queries"][0]["title"] == "Query"
        assert result["queries"][0]["explanation"] == ""
        assert result["assumptions"] == []

    def test_out_of_bounds_recommended_index_clamped(self):
        text = _make_json_output(
            [{"title": "Q", "sql": "SELECT 1", "explanation": ""}],
            recommended_index=5,
        )
        result = _parse_llm_response(text)
        assert result["recommended_index"] == 0

    def test_empty_queries_gets_default(self):
        text = json.dumps({"queries": [], "recommended_index": 0, "assumptions": []})
        result = _parse_llm_response(text)
        assert len(result["queries"]) == 1
        assert result["queries"][0]["sql"] == ""


class TestBuildChatRequest:
    def test_schema_context_populates_default_template(self):
        req = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="any",
            dialect=SQLDialect.postgresql,
            schema_context="CREATE TABLE foo (id INT);",
        )
        chat = _build_chat_request(req)
        system = chat.messages[0].content
        assert "CREATE TABLE foo (id INT);" in system
        assert "## Database Schema" in system

    def test_system_prompt_override_bypasses_schema_context(self):
        req = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="any",
            dialect=SQLDialect.postgresql,
            schema_context="IGNORED",
            system_prompt="You are a SQL bot. {dialect_guidance}",
        )
        chat = _build_chat_request(req)
        system = chat.messages[0].content
        assert "IGNORED" not in system
        assert "You are a SQL bot" in system


class TestGenerateSQL:
    @pytest.fixture
    def base_request(self) -> NL2SQLRequest:
        return NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="Show me all active users",
            dialect=SQLDialect.postgresql,
        )

    async def test_generates_valid_sql(self, base_request: NL2SQLRequest):
        output = _make_json_output(
            [
                {
                    "title": "Active users",
                    "sql": "SELECT * FROM users WHERE active = true",
                    "explanation": "Fetches active users",
                }
            ]
        )
        adapter = _make_mock_adapter(output)
        result = await generate_sql(base_request, adapter)

        assert result.generated_sql == "SELECT * FROM users WHERE active = true"
        assert result.explanation == "Fetches active users"
        assert len(result.queries) == 1
        assert result.queries[0].title == "Active users"
        assert result.dialect == SQLDialect.postgresql
        assert result.validation.is_valid is True
        assert result.usage["total_tokens"] == 150

    async def test_generates_multiple_queries(self):
        request = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="Top 10 employees by salary",
            dialect=SQLDialect.postgresql,
        )
        output = _make_json_output(
            [
                {
                    "title": "Simple LIMIT",
                    "sql": "SELECT * FROM employees ORDER BY salary DESC LIMIT 10",
                    "explanation": "No tie handling",
                },
                {
                    "title": "With DENSE_RANK",
                    "sql": (
                        "SELECT * FROM (SELECT *, DENSE_RANK() OVER (ORDER BY salary DESC) "
                        "AS rnk FROM employees) t WHERE rnk <= 10"
                    ),
                    "explanation": "Handles ties",
                },
            ],
            recommended_index=0,
            assumptions=["employees table has a salary column"],
        )
        adapter = _make_mock_adapter(output)
        result = await generate_sql(request, adapter)

        assert len(result.queries) == 2
        assert result.recommended_index == 0
        assert result.generated_sql == result.queries[0].sql
        assert len(result.assumptions) == 1

    async def test_generates_with_sandbox_ddl(self):
        request = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="Count all users",
            dialect=SQLDialect.postgresql,
            sandbox_ddl="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
        )
        output = _make_json_output(
            [
                {"title": "Count users", "sql": "SELECT COUNT(*) FROM users", "explanation": "Counts users"},
            ]
        )
        adapter = _make_mock_adapter(output)
        result = await generate_sql(request, adapter)

        assert result.validation.is_valid is True
        assert result.validation.sandbox_execution_success is True

    async def test_handles_invalid_generated_sql(self, base_request: NL2SQLRequest):
        output = _make_json_output(
            [
                {"title": "Bad query", "sql": "SELEC broken syntax here", "explanation": ""},
            ]
        )
        adapter = _make_mock_adapter(output)
        result = await generate_sql(base_request, adapter)

        assert result.validation.is_valid is False
        assert len(result.validation.syntax_errors) > 0

    async def test_adapter_called_with_correct_messages(self, base_request: NL2SQLRequest):
        output = _make_json_output([{"title": "Q", "sql": "SELECT 1", "explanation": ""}])
        adapter = _make_mock_adapter(output)
        await generate_sql(base_request, adapter)

        adapter.chat.assert_called_once()
        chat_req = adapter.chat.call_args[0][0]
        assert len(chat_req.messages) == 2
        assert chat_req.messages[0].role == "system"
        assert chat_req.messages[1].role == "user"
        assert chat_req.messages[1].content == "Show me all active users"

    async def test_openai_provider_gets_response_format(self, base_request: NL2SQLRequest):
        output = _make_json_output([{"title": "Q", "sql": "SELECT 1", "explanation": ""}])
        adapter = _make_mock_adapter(output)
        await generate_sql(base_request, adapter)

        chat_req = adapter.chat.call_args[0][0]
        assert "response_format" in chat_req.provider_options
        assert chat_req.provider_options["response_format"]["type"] == "json_schema"

    async def test_anthropic_provider_no_response_format(self):
        request = NL2SQLRequest(
            provider="anthropic",
            model="claude-sonnet-4-6",
            natural_language="Show me users",
            dialect=SQLDialect.postgresql,
        )
        output = _make_json_output([{"title": "Q", "sql": "SELECT 1", "explanation": ""}])
        adapter = _make_mock_adapter(output)
        await generate_sql(request, adapter)

        chat_req = adapter.chat.call_args[0][0]
        assert "response_format" not in chat_req.provider_options

    async def test_adapter_called_with_conversation_history(self):
        request = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="Now add a LIMIT 10",
            dialect=SQLDialect.postgresql,
            conversation_history=[
                NL2SQLHistoryMessage(role="user", content="Show me all users"),
                NL2SQLHistoryMessage(role="assistant", content="SELECT * FROM users"),
            ],
        )
        output = _make_json_output(
            [
                {"title": "With limit", "sql": "SELECT * FROM users LIMIT 10", "explanation": ""},
            ]
        )
        adapter = _make_mock_adapter(output)
        await generate_sql(request, adapter)

        adapter.chat.assert_called_once()
        chat_req = adapter.chat.call_args[0][0]
        assert len(chat_req.messages) == 4
        assert chat_req.messages[0].role == "system"
        assert chat_req.messages[1].role == "user"
        assert chat_req.messages[1].content == "Show me all users"
        assert chat_req.messages[2].role == "assistant"
        assert chat_req.messages[2].content == "SELECT * FROM users"
        assert chat_req.messages[3].role == "user"
        assert chat_req.messages[3].content == "Now add a LIMIT 10"

    async def test_fallback_when_llm_returns_raw_sql(self, base_request: NL2SQLRequest):
        adapter = _make_mock_adapter("SELECT * FROM users WHERE active = true")
        result = await generate_sql(base_request, adapter)

        assert result.generated_sql == "SELECT * FROM users WHERE active = true"
        assert len(result.queries) == 1
        assert result.queries[0].title == "Generated query"
        assert result.raw_llm_output == "SELECT * FROM users WHERE active = true"


class TestStreamGenerateSQL:
    async def test_stream_collects_deltas_and_yields_single_final_with_raw(self):
        request = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="Top employees",
            dialect=SQLDialect.postgresql,
        )
        output = _make_json_output(
            [
                {"title": "Top", "sql": "SELECT * FROM emp ORDER BY salary DESC LIMIT 10", "explanation": ""},
            ]
        )
        combined = ""

        async def fake_stream():
            nonlocal combined
            for chunk in (output[:20], output[20:]):
                combined += chunk
                yield StreamDelta(text=chunk)
            yield StreamFinal(
                response=NormalizedChatResponse(
                    output_text=combined,
                    finish_reason="stop",
                    usage=UsageInfo(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                ),
            )

        adapter = AsyncMock(spec=ProviderAdapter)
        adapter.stream_chat.return_value = fake_stream()

        events: list = []
        async for ev in stream_generate_sql(request, adapter):
            events.append(ev)

        assert len(events) == 1
        final = events[0]
        assert final.generated_sql == "SELECT * FROM emp ORDER BY salary DESC LIMIT 10"
        assert final.raw_llm_output == output
