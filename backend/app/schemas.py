from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Tool-calling primitives ─────────────────────────────────────────────────
class ToolCallFunction(BaseModel):
    name: str
    arguments: str  # JSON-encoded string


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction


class ToolFunctionDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


class ToolDefinitionRequest(BaseModel):
    type: str = "function"
    function: ToolFunctionDefinition


# ── Messages ────────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str  # system | user | assistant | tool
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


# ── Chat Request ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    provider: str
    model: str
    messages: list[Message]
    temperature: float | None = 0.7
    max_tokens: int = 1024
    tools: list[ToolDefinitionRequest] | None = None
    tool_choice: str | None = None
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
    tool_calls: list[ToolCall] | None = None
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
    conversation_id: str | None = None
    run_id: str | None = None


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
    conversation_id: str | None = None

    model_config = {"from_attributes": True}


class PaginatedRuns(BaseModel):
    items: list[RunSummary]
    total: int
    page: int
    per_page: int


# ── Conversation schemas ────────────────────────────────────────────────────
class ConversationTurnRequest(BaseModel):
    conversation_id: str | None = None
    provider: str
    model: str
    message: str
    system_prompt: str | None = None
    temperature: float | None = 0.7
    max_tokens: int = 1024
    provider_options: dict[str, Any] = Field(default_factory=dict)
    tool_mode: Literal["off", "auto", "manual"] = "off"
    tool_names: list[str] | None = None


class ConversationMessageSchema(BaseModel):
    id: str
    role: str
    content: str
    ordinal: int
    created_at: datetime
    run_id: str | None = None
    metadata_json: str | None = None

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    provider: str
    model: str
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    provider: str
    model: str
    system_prompt: str | None = None
    config_json: str | None = None
    messages: list[ConversationMessageSchema] = []

    model_config = {"from_attributes": True}


class PaginatedConversations(BaseModel):
    items: list[ConversationSummary]
    total: int
    page: int
    per_page: int


class TurnResponse(BaseModel):
    conversation_id: str
    run_id: str
    response: NormalizedChatResponse
    latency_ms: float
