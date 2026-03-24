from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.adapters.base import ProviderAdapter
from app.schemas import NormalizedChatResponse, UsageInfo


def _mock_adapter(output_text: str = "SELECT id FROM users") -> ProviderAdapter:
    adapter = AsyncMock(spec=ProviderAdapter)
    adapter.name = "openai"
    adapter.chat.return_value = NormalizedChatResponse(
        output_text=output_text,
        finish_reason="stop",
        usage=UsageInfo(prompt_tokens=50, completion_tokens=30, total_tokens=80),
    )
    return adapter


class TestGenerateEndpoint:
    async def test_generate_success(self, client: AsyncClient):
        adapter = _mock_adapter("SELECT id, name FROM users WHERE active = true\n-- Explanation: Active users")
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
    async def test_execute_unsupported_scheme(self, client: AsyncClient):
        resp = await client.post("/api/querylab/execute", json={
            "sql": "SELECT 1",
            "dialect": "postgresql",
            "connection_string": "unsupported://localhost/db",
            "timeout_seconds": 5,
        })
        assert resp.status_code == 400

    async def test_execute_missing_connection_string(self, client: AsyncClient):
        resp = await client.post("/api/querylab/execute", json={
            "sql": "SELECT 1",
            "dialect": "postgresql",
        })
        assert resp.status_code == 422
