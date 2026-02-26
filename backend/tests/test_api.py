"""Tests for API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "available_providers" in data


@pytest.mark.asyncio
async def test_list_runs_empty(client: AsyncClient):
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_run_not_found(client: AsyncClient):
    resp = await client.get("/api/runs/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_invalid_provider(client: AsyncClient):
    resp = await client.post(
        "/api/chat",
        json={
            "provider": "nonexistent",
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 400
    assert "not available" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_run_not_found(client: AsyncClient):
    resp = await client.delete("/api/runs/nonexistent")
    assert resp.status_code == 404
