from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Messages ────────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None


# ── Chat Request ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    provider: str
    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int = 1024
    provider_options: dict[str, Any] = Field(default_factory=dict)


# ── Normalized Response ─────────────────────────────────────────────────────
class UsageInfo(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class NormalizedChatResponse(BaseModel):
    output_text: str
    finish_reason: str | None = None
    provider_response_id: str | None = None
    usage: UsageInfo = Field(default_factory=UsageInfo)
    raw: dict[str, Any] = Field(default_factory=dict)


# ── SSE Stream Events ──────────────────────────────────────────────────────
class StreamDelta(BaseModel):
    type: str = "delta"
    text: str


class StreamMeta(BaseModel):
    type: str = "meta"
    provider: str
    model: str


class StreamFinal(BaseModel):
    type: str = "final"
    response: NormalizedChatResponse


class StreamError(BaseModel):
    type: str = "error"
    message: str


# ── Run schemas ─────────────────────────────────────────────────────────────
class RunSummary(BaseModel):
    id: str
    created_at: datetime
    provider: str
    model: str
    status: str
    latency_ms: float | None = None
    total_tokens: int | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class RunDetail(RunSummary):
    request_json: str
    normalized_response_json: str | None = None
    raw_response_json: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tags: str | None = None
    trace_id: str | None = None
    parent_run_id: str | None = None

    model_config = {"from_attributes": True}


class PaginatedRuns(BaseModel):
    items: list[RunSummary]
    total: int
    page: int
    per_page: int
