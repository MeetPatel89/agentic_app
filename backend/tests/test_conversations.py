"""Tests for conversation endpoints and service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import NormalizedChatResponse, UsageInfo
from app.services.conversation import ConversationService

# ── Service-level tests ─────────────────────────────────────────────────────


async def test_create_conversation(db_session: AsyncSession):
    svc = ConversationService()
    conv = await svc.create_conversation(
        db_session, provider="openai", model="gpt-4o-mini", system_prompt="Be helpful."
    )
    await db_session.commit()
    assert conv.id is not None
    assert conv.provider == "openai"
    assert conv.model == "gpt-4o-mini"
    assert conv.system_prompt == "Be helpful."


async def test_append_and_get_messages(db_session: AsyncSession):
    svc = ConversationService()
    conv = await svc.create_conversation(
        db_session, provider="openai", model="gpt-4o-mini"
    )
    await svc.append_message(db_session, conversation_id=conv.id, role="user", content="Hello")
    await svc.append_message(db_session, conversation_id=conv.id, role="assistant", content="Hi there!")
    await svc.append_message(db_session, conversation_id=conv.id, role="user", content="How are you?")
    await db_session.commit()

    messages = await svc.get_messages(db_session, conv.id)
    assert len(messages) == 3
    assert messages[0].ordinal == 0
    assert messages[1].ordinal == 1
    assert messages[2].ordinal == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


async def test_build_chat_request_includes_history(db_session: AsyncSession):
    svc = ConversationService()
    conv = await svc.create_conversation(
        db_session, provider="openai", model="gpt-4o-mini", system_prompt="You are a bot."
    )
    await svc.append_message(db_session, conversation_id=conv.id, role="user", content="Hello")
    await svc.append_message(db_session, conversation_id=conv.id, role="assistant", content="Hi!")
    await db_session.commit()

    chat_req = await svc.build_chat_request(
        db_session, conversation=conv, new_user_message="What is 2+2?"
    )
    assert chat_req.provider == "openai"
    assert chat_req.model == "gpt-4o-mini"
    # system prompt + 2 history messages + new user message
    assert len(chat_req.messages) == 4
    assert chat_req.messages[0].role == "system"
    assert chat_req.messages[0].content == "You are a bot."
    assert chat_req.messages[-1].role == "user"
    assert chat_req.messages[-1].content == "What is 2+2?"


async def test_sliding_window_trims_old_messages(db_session: AsyncSession):
    svc = ConversationService()
    conv = await svc.create_conversation(
        db_session, provider="openai", model="gpt-4o-mini"
    )
    for i in range(10):
        await svc.append_message(
            db_session, conversation_id=conv.id, role="user", content=f"msg {i}"
        )
    await db_session.commit()

    chat_req = await svc.build_chat_request(
        db_session, conversation=conv, new_user_message="latest", window_size=3,
    )
    # 3 windowed messages + 1 new user message = 4 total
    assert len(chat_req.messages) == 4
    assert chat_req.messages[0].content == "msg 7"
    assert chat_req.messages[-1].content == "latest"


async def test_get_last_run_id(db_session: AsyncSession):
    svc = ConversationService()
    conv = await svc.create_conversation(
        db_session, provider="openai", model="gpt-4o-mini"
    )
    await svc.append_message(
        db_session, conversation_id=conv.id, role="assistant", content="Hi", run_id="run-1"
    )
    await svc.append_message(
        db_session, conversation_id=conv.id, role="assistant", content="Bye", run_id="run-2"
    )
    await db_session.commit()

    last = await svc.get_last_run_id(db_session, conv.id)
    assert last == "run-2"


async def test_get_last_run_id_none_when_empty(db_session: AsyncSession):
    svc = ConversationService()
    conv = await svc.create_conversation(
        db_session, provider="openai", model="gpt-4o-mini"
    )
    await db_session.commit()

    last = await svc.get_last_run_id(db_session, conv.id)
    assert last is None


# ── Conversation CRUD endpoint tests ────────────────────────────────────────


async def test_list_conversations_empty(client: AsyncClient):
    resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_conversation_not_found(client: AsyncClient):
    resp = await client.get("/api/conversations/nonexistent")
    assert resp.status_code == 404


async def test_delete_conversation_not_found(client: AsyncClient):
    resp = await client.delete("/api/conversations/nonexistent")
    assert resp.status_code == 404


# ── Turn-based endpoint tests ───────────────────────────────────────────────

MOCK_RESPONSE = NormalizedChatResponse(
    output_text="Hello, I'm an assistant!",
    finish_reason="stop",
    usage=UsageInfo(prompt_tokens=10, completion_tokens=8, total_tokens=18),
)


async def test_chat_turn_creates_conversation(client: AsyncClient):
    with patch("app.routers.chat.get_adapter") as mock_get:
        adapter = AsyncMock()
        adapter.chat = AsyncMock(return_value=MOCK_RESPONSE)
        mock_get.return_value = adapter

        resp = await client.post(
            "/api/chat/turn",
            json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "message": "Hello!",
                "system_prompt": "Be helpful.",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert "run_id" in data
    assert data["response"]["output_text"] == "Hello, I'm an assistant!"


async def test_chat_turn_continues_conversation(client: AsyncClient):
    with patch("app.routers.chat.get_adapter") as mock_get:
        adapter = AsyncMock()
        adapter.chat = AsyncMock(return_value=MOCK_RESPONSE)
        mock_get.return_value = adapter

        # First turn
        resp1 = await client.post(
            "/api/chat/turn",
            json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "message": "Hello!",
                "system_prompt": "Be helpful.",
            },
        )
        conv_id = resp1.json()["conversation_id"]

        # Second turn
        resp2 = await client.post(
            "/api/chat/turn",
            json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "message": "How are you?",
                "conversation_id": conv_id,
            },
        )

    assert resp2.status_code == 200
    assert resp2.json()["conversation_id"] == conv_id

    # Verify conversation has messages
    conv_resp = await client.get(f"/api/conversations/{conv_id}")
    assert conv_resp.status_code == 200
    messages = conv_resp.json()["messages"]
    # 2 user messages + 2 assistant messages = 4
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello!"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "How are you?"
    assert messages[3]["role"] == "assistant"


async def test_chat_turn_invalid_provider(client: AsyncClient):
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


async def test_chat_turn_conversation_not_found(client: AsyncClient):
    resp = await client.post(
        "/api/chat/turn",
        json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "message": "hi",
            "conversation_id": "nonexistent-id",
        },
    )
    assert resp.status_code == 404


async def test_conversation_crud_lifecycle(client: AsyncClient):
    """Create via turn, list, get detail, update title, delete."""
    with patch("app.routers.chat.get_adapter") as mock_get:
        adapter = AsyncMock()
        adapter.chat = AsyncMock(return_value=MOCK_RESPONSE)
        mock_get.return_value = adapter

        resp = await client.post(
            "/api/chat/turn",
            json={"provider": "openai", "model": "gpt-4o-mini", "message": "Hello!"},
        )
    conv_id = resp.json()["conversation_id"]

    # List
    list_resp = await client.get("/api/conversations")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # Detail
    detail_resp = await client.get(f"/api/conversations/{conv_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["provider"] == "openai"

    # Update title
    patch_resp = await client.patch(
        f"/api/conversations/{conv_id}", json={"title": "Test Chat"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Test Chat"

    # Delete
    del_resp = await client.delete(f"/api/conversations/{conv_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == conv_id

    # Verify gone
    gone_resp = await client.get(f"/api/conversations/{conv_id}")
    assert gone_resp.status_code == 404


async def test_chat_turn_sets_trace_id_and_parent_run_id(client: AsyncClient):
    with patch("app.routers.chat.get_adapter") as mock_get:
        adapter = AsyncMock()
        adapter.chat = AsyncMock(return_value=MOCK_RESPONSE)
        mock_get.return_value = adapter

        resp1 = await client.post(
            "/api/chat/turn",
            json={"provider": "openai", "model": "gpt-4o-mini", "message": "Turn 1"},
        )
        run_id_1 = resp1.json()["run_id"]

        conv_id = resp1.json()["conversation_id"]
        resp2 = await client.post(
            "/api/chat/turn",
            json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "message": "Turn 2",
                "conversation_id": conv_id,
            },
        )

    # Verify first run has trace_id
    run1 = await client.get(f"/api/runs/{run_id_1}")
    assert run1.status_code == 200
    assert run1.json()["trace_id"] is not None
    assert run1.json()["conversation_id"] == conv_id

    # Verify second run chains parent_run_id
    run_id_2 = resp2.json()["run_id"]
    run2 = await client.get(f"/api/runs/{run_id_2}")
    assert run2.status_code == 200
    assert run2.json()["parent_run_id"] == run_id_1


# ── Backward compatibility ──────────────────────────────────────────────────


async def test_legacy_chat_endpoint_still_works(client: AsyncClient):
    """Existing /api/chat endpoint is unchanged."""
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
