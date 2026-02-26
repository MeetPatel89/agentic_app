"""Tests for adapter normalization logic."""

from __future__ import annotations

from app.schemas import ChatRequest, Message, NormalizedChatResponse, UsageInfo


def _sample_request() -> ChatRequest:
    return ChatRequest(
        provider="openai",
        model="gpt-4o-mini",
        messages=[
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
        ],
        temperature=0.5,
        max_tokens=100,
    )


def test_normalized_response_shape():
    resp = NormalizedChatResponse(
        output_text="Hello!",
        finish_reason="stop",
        provider_response_id="resp-123",
        usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        raw={"id": "resp-123", "choices": []},
    )
    assert resp.output_text == "Hello!"
    assert resp.usage.total_tokens == 15
    d = resp.model_dump()
    assert "output_text" in d
    assert "raw" in d


def test_chat_request_defaults():
    req = _sample_request()
    assert req.temperature == 0.5
    assert req.max_tokens == 100
    assert len(req.messages) == 2
    assert req.provider_options == {}


def test_chat_request_serialization():
    req = _sample_request()
    json_str = req.model_dump_json()
    restored = ChatRequest.model_validate_json(json_str)
    assert restored.provider == req.provider
    assert len(restored.messages) == 2
