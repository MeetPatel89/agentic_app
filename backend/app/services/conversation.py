from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Conversation, ConversationMessage
from app.schemas import ChatRequest, Message

if TYPE_CHECKING:
    from app.agentic.memory import MemoryStore

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SIZE = 50


class ConversationService:
    """Manages multi-turn conversation state.

    Accepts an optional MemoryStore for Approach 3 extensibility —
    when provided, build_chat_request can prepend retrieved memories.
    """

    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self._memory_store = memory_store

    async def create_conversation(
        self,
        db: AsyncSession,
        *,
        provider: str,
        model: str,
        system_prompt: str | None = None,
        title: str | None = None,
    ) -> Conversation:
        conv = Conversation(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            title=title,
        )
        db.add(conv)
        await db.flush()
        return conv

    async def get_conversation(
        self, db: AsyncSession, conversation_id: str
    ) -> Conversation | None:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def append_message(
        self,
        db: AsyncSession,
        *,
        conversation_id: str,
        role: str,
        content: str,
        run_id: str | None = None,
    ) -> ConversationMessage:
        next_ordinal_q = await db.execute(
            select(func.coalesce(func.max(ConversationMessage.ordinal), -1) + 1).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )
        ordinal = next_ordinal_q.scalar_one()

        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            ordinal=ordinal,
            run_id=run_id,
        )
        db.add(msg)
        await db.flush()
        return msg

    async def get_messages(
        self, db: AsyncSession, conversation_id: str
    ) -> list[ConversationMessage]:
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.ordinal)
        )
        return list(result.scalars().all())

    async def build_chat_request(
        self,
        db: AsyncSession,
        *,
        conversation: Conversation,
        new_user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        provider_options: dict | None = None,
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> ChatRequest:
        """Assemble a full ChatRequest from conversation history + new message.

        Extension point for Approach 3: when self._memory_store is set,
        retrieved memories/summaries can be prepended to the message list
        before the conversation history.
        """
        messages: list[Message] = []

        # --- Approach 3 hook: prepend retrieved memories ---
        if self._memory_store is not None:
            memories = await self._memory_store.search(new_user_message, top_k=5)
            for mem in memories:
                messages.append(Message(role="system", content=str(mem)))

        if conversation.system_prompt:
            messages.append(Message(role="system", content=conversation.system_prompt))

        history = await self.get_messages(db, conversation.id)
        history = self._apply_sliding_window(history, window_size)

        for msg in history:
            messages.append(Message(role=msg.role, content=msg.content))

        messages.append(Message(role="user", content=new_user_message))

        return ChatRequest(
            provider=conversation.provider,
            model=conversation.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_options=provider_options or {},
        )

    @staticmethod
    def _apply_sliding_window(
        messages: list[ConversationMessage], window_size: int
    ) -> list[ConversationMessage]:
        if len(messages) <= window_size:
            return messages
        return messages[-window_size:]

    async def get_last_run_id(
        self, db: AsyncSession, conversation_id: str
    ) -> str | None:
        """Return the run_id of the last assistant message (for parent_run_id chaining)."""
        result = await db.execute(
            select(ConversationMessage.run_id)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.role == "assistant",
                ConversationMessage.run_id.isnot(None),
            )
            .order_by(ConversationMessage.ordinal.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


conversation_service = ConversationService()
