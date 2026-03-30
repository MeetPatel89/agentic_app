from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.adapters.base import ProviderAdapter
from app.nl2sql.schemas import SQLExecuteResponse
from app.schemas import NormalizedChatResponse, UsageInfo


def _json_output(
    queries: list[dict] | None = None,
    recommended_index: int = 0,
    assumptions: list[str] | None = None,
) -> str:
    if queries is None:
        queries = [{"title": "Query", "sql": "SELECT id FROM users", "explanation": "Gets user IDs"}]
    return json.dumps({
        "queries": queries,
        "recommended_index": recommended_index,
        "assumptions": assumptions or [],
    })


def _mock_adapter(output_text: str | None = None) -> ProviderAdapter:
    adapter = AsyncMock(spec=ProviderAdapter)
    adapter.name = "openai"
    adapter.chat.return_value = NormalizedChatResponse(
        output_text=output_text or _json_output(),
        finish_reason="stop",
        usage=UsageInfo(prompt_tokens=50, completion_tokens=30, total_tokens=80),
    )
    return adapter


class TestGenerateEndpoint:
    async def test_generate_success(self, client: AsyncClient):
        output = _json_output([{
            "title": "Active users",
            "sql": "SELECT id, name FROM users WHERE active = true",
            "explanation": "Active users",
        }])
        adapter = _mock_adapter(output)
        with patch("app.nl2sql.router.get_adapter", return_value=adapter):
            resp = await client.post("/api/querylab/generate", json={
                "provider": "openai",
                "model": "gpt-4o",
                "natural_language": "Show me active users",
                "dialect": "postgresql",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "generated_sql" in data
        assert data["dialect"] == "postgresql"
        assert data["validation"]["is_valid"] is True
        assert data["run_id"] is not None
        assert len(data["queries"]) == 1
        assert data["queries"][0]["title"] == "Active users"
        assert data["raw_llm_output"] == output

    async def test_generate_provider_not_available(self, client: AsyncClient):
        with patch("app.nl2sql.router.get_adapter", return_value=None):
            resp = await client.post("/api/querylab/generate", json={
                "provider": "nonexistent",
                "model": "gpt-4o",
                "natural_language": "Show me users",
            })
        assert resp.status_code == 400

    async def test_generate_missing_natural_language(self, client: AsyncClient):
        resp = await client.post("/api/querylab/generate", json={
            "provider": "openai",
            "model": "gpt-4o",
        })
        assert resp.status_code == 422

    async def test_generate_with_conversation_history(self, client: AsyncClient):
        output = _json_output([
            {"title": "With limit", "sql": "SELECT * FROM users LIMIT 10", "explanation": ""},
        ])
        adapter = _mock_adapter(output)
        with patch("app.nl2sql.router.get_adapter", return_value=adapter):
            resp = await client.post("/api/querylab/generate", json={
                "provider": "openai",
                "model": "gpt-4o",
                "natural_language": "Now add a LIMIT 10",
                "dialect": "postgresql",
                "conversation_history": [
                    {"role": "user", "content": "Show me all users"},
                    {"role": "assistant", "content": "SELECT * FROM users"},
                ],
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "generated_sql" in data
        # Verify history was forwarded to adapter
        chat_req = adapter.chat.call_args[0][0]
        assert len(chat_req.messages) == 4


class TestValidateEndpoint:
    async def test_validate_valid_sql(self, client: AsyncClient):
        resp = await client.post("/api/querylab/validate", json={
            "sql": "SELECT id FROM users WHERE active = true",
            "dialect": "postgresql",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True

    async def test_validate_invalid_sql(self, client: AsyncClient):
        resp = await client.post("/api/querylab/validate", json={
            "sql": "SELEC id FROM",
            "dialect": "postgresql",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert len(data["syntax_errors"]) > 0

    async def test_validate_with_sandbox_ddl(self, client: AsyncClient):
        resp = await client.post("/api/querylab/validate", json={
            "sql": "SELECT id, name FROM users",
            "dialect": "postgresql",
            "sandbox_ddl": "CREATE TABLE users (id INTEGER, name TEXT);",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["sandbox_execution_success"] is True

    async def test_validate_sandbox_column_mismatch(self, client: AsyncClient):
        resp = await client.post("/api/querylab/validate", json={
            "sql": "SELECT nonexistent FROM users",
            "dialect": "postgresql",
            "sandbox_ddl": "CREATE TABLE users (id INTEGER, name TEXT);",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_execution_success"] is False


class TestExecuteEndpoint:
    async def test_execute_success(self, client: AsyncClient):
        mocked = SQLExecuteResponse(
            columns=["val"],
            rows=[[1]],
            row_count=1,
            execution_time_ms=1.0,
            truncated=False,
        )
        with patch("app.nl2sql.router.executor.execute_sql", new=AsyncMock(return_value=mocked)):
            resp = await client.post("/api/querylab/execute", json={
                "sql": "SELECT 1 AS val",
                "dialect": "sqlite",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["columns"] == ["val"]
        assert data["row_count"] == 1

    async def test_execute_invalid_sql(self, client: AsyncClient):
        resp = await client.post("/api/querylab/execute", json={
            "sql": "INVALID SQL STATEMENT",
            "dialect": "sqlite",
        })
        assert resp.status_code == 400

    async def test_execute_missing_sql(self, client: AsyncClient):
        resp = await client.post("/api/querylab/execute", json={
            "dialect": "sqlite",
        })
        assert resp.status_code == 422

    async def test_execute_rejects_write_in_read_only_mode(self, client: AsyncClient):
        resp = await client.post("/api/querylab/execute", json={
            "sql": "INSERT INTO users (id) VALUES (1)",
            "dialect": "sqlite",
        })
        assert resp.status_code == 400
        assert "Read-only execution mode" in resp.json()["detail"]

    async def test_execute_rejects_multi_statement_payload(self, client: AsyncClient):
        resp = await client.post("/api/querylab/execute", json={
            "sql": "SELECT 1; SELECT 2;",
            "dialect": "sqlite",
        })
        assert resp.status_code == 400
        assert "exactly one SQL statement" in resp.json()["detail"]

    async def test_execute_allows_trailing_comment_after_semicolon(self, client: AsyncClient):
        """SQL with a trailing comment after semicolon should not be rejected."""
        mocked = SQLExecuteResponse(
            columns=["val"],
            rows=[[1]],
            row_count=1,
            execution_time_ms=1.0,
            truncated=False,
        )
        with patch("app.nl2sql.router.executor.execute_sql", new=AsyncMock(return_value=mocked)):
            resp = await client.post("/api/querylab/execute", json={
                "sql": "SELECT 1 AS val;\n-- This is an explanation comment",
                "dialect": "sqlite",
            })
        assert resp.status_code == 200
