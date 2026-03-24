from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.adapters.base import ProviderAdapter
from app.nl2sql.schemas import NL2SQLRequest, SQLDialect
from app.nl2sql.service import _extract_sql_and_explanation, generate_sql
from app.schemas import NormalizedChatResponse, UsageInfo


def _make_mock_adapter(output_text: str) -> ProviderAdapter:
    adapter = AsyncMock(spec=ProviderAdapter)
    adapter.chat.return_value = NormalizedChatResponse(
        output_text=output_text,
        finish_reason="stop",
        usage=UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    return adapter


class TestExtractSQLAndExplanation:
    def test_fenced_sql_block(self):
        text = "```sql\nSELECT id FROM users;\n```\n-- Explanation: Gets all user IDs"
        sql, explanation = _extract_sql_and_explanation(text)
        assert sql == "SELECT id FROM users;"
        assert "user IDs" in explanation

    def test_raw_sql_with_explanation(self):
        text = "SELECT id FROM users\n-- Explanation: Gets all user IDs"
        sql, explanation = _extract_sql_and_explanation(text)
        assert sql == "SELECT id FROM users"
        assert "user IDs" in explanation

    def test_raw_sql_no_explanation(self):
        text = "SELECT id FROM users WHERE active = true"
        sql, explanation = _extract_sql_and_explanation(text)
        assert sql == "SELECT id FROM users WHERE active = true"
        assert explanation == ""

    def test_fenced_block_no_language(self):
        text = "```\nSELECT 1;\n```"
        sql, explanation = _extract_sql_and_explanation(text)
        assert sql == "SELECT 1;"

    def test_explanation_inside_fence(self):
        text = "```sql\nSELECT id FROM users;\n-- Explanation: Gets IDs\n```"
        sql, explanation = _extract_sql_and_explanation(text)
        assert sql == "SELECT id FROM users;"
        assert "Gets IDs" in explanation


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
        adapter = _make_mock_adapter("SELECT * FROM users WHERE active = true\n-- Explanation: Fetches active users")
        result = await generate_sql(base_request, adapter)

        assert result.generated_sql == "SELECT * FROM users WHERE active = true"
        assert result.explanation == "Fetches active users"
        assert result.dialect == SQLDialect.postgresql
        assert result.validation.is_valid is True
        assert result.usage["total_tokens"] == 150

    async def test_generates_with_sandbox_ddl(self):
        request = NL2SQLRequest(
            provider="openai",
            model="gpt-4o",
            natural_language="Count all users",
            dialect=SQLDialect.postgresql,
            sandbox_ddl="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
        )
        adapter = _make_mock_adapter("SELECT COUNT(*) FROM users\n-- Explanation: Counts users")
        result = await generate_sql(request, adapter)

        assert result.validation.is_valid is True
        assert result.validation.sandbox_execution_success is True

    async def test_handles_invalid_generated_sql(self, base_request: NL2SQLRequest):
        adapter = _make_mock_adapter("SELEC broken syntax here")
        result = await generate_sql(base_request, adapter)

        assert result.validation.is_valid is False
        assert len(result.validation.syntax_errors) > 0

    async def test_adapter_called_with_correct_messages(self, base_request: NL2SQLRequest):
        adapter = _make_mock_adapter("SELECT 1")
        await generate_sql(base_request, adapter)

        adapter.chat.assert_called_once()
        chat_req = adapter.chat.call_args[0][0]
        assert len(chat_req.messages) == 2
        assert chat_req.messages[0].role == "system"
        assert chat_req.messages[1].role == "user"
        assert chat_req.messages[1].content == "Show me all active users"
