"""Tests for API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.adapters.openai_adapter import OpenAIAdapter
from app.schemas import ChatRequest


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


class TestReasoningModelTemperature:
    """Reasoning models must not receive a temperature parameter."""

    @pytest.mark.parametrize("model", ["o1", "o1-mini", "o3", "o3-mini", "o4-mini", "gpt-5-mini", "gpt-5.1-mini"])
    def test_is_reasoning_model(self, model: str):
        assert OpenAIAdapter._is_reasoning_model(model) is True

    @pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"])
    def test_is_not_reasoning_model(self, model: str):
        assert OpenAIAdapter._is_reasoning_model(model) is False

    def test_sampling_kwargs_omits_temperature_for_reasoning_model(self):
        adapter = OpenAIAdapter.__new__(OpenAIAdapter)
        req = ChatRequest(
            provider="openai",
            model="gpt-5.1-mini",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
        )
        kwargs = adapter._build_sampling_kwargs(req)
        assert "temperature" not in kwargs

    def test_sampling_kwargs_includes_temperature_for_normal_model(self):
        adapter = OpenAIAdapter.__new__(OpenAIAdapter)
        req = ChatRequest(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
        )
        kwargs = adapter._build_sampling_kwargs(req)
        assert kwargs["temperature"] == 0.7

    def test_sampling_kwargs_omits_temperature_when_none(self):
        adapter = OpenAIAdapter.__new__(OpenAIAdapter)
        req = ChatRequest(
            provider="openai",
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            temperature=None,
        )
        kwargs = adapter._build_sampling_kwargs(req)
        assert "temperature" not in kwargs
