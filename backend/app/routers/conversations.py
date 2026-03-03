from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, ConversationMessage
from app.schemas import (
    ConversationDetail,
    ConversationMessageSchema,
    ConversationSummary,
    PaginatedConversations,
)
from app.services.conversation import conversation_service

router = APIRouter(prefix="/api")


@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedConversations:
    offset = (page - 1) * per_page

    total_q = await db.execute(select(func.count(Conversation.id)))
    total = total_q.scalar_one()

    # Subquery for message counts
    msg_count_sq = (
        select(
            ConversationMessage.conversation_id,
            func.count(ConversationMessage.id).label("msg_count"),
        )
        .group_by(ConversationMessage.conversation_id)
        .subquery()
    )

    q = (
        select(Conversation, func.coalesce(msg_count_sq.c.msg_count, 0).label("message_count"))
        .outerjoin(msg_count_sq, Conversation.id == msg_count_sq.c.conversation_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(q)

    items = []
    for conv, msg_count in result.all():
        items.append(
            ConversationSummary(
                id=conv.id,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                title=conv.title,
                provider=conv.provider,
                model=conv.model,
                message_count=msg_count,
            )
        )

    return PaginatedConversations(items=items, total=total, page=page, per_page=per_page)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, db: AsyncSession = Depends(get_db)
) -> ConversationDetail:
    conv = await conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetail(
        id=conv.id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        title=conv.title,
        provider=conv.provider,
        model=conv.model,
        system_prompt=conv.system_prompt,
        config_json=conv.config_json,
        messages=[ConversationMessageSchema.model_validate(m) for m in conv.messages],
    )


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    conv = await conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if "title" in body:
        conv.title = body["title"]
    await db.commit()
    return {"id": conv.id, "title": conv.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    conv = await conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"deleted": conversation_id}
