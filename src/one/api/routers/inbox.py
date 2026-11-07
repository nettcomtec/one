"""Inbox REST — list conversations, read a thread, reply, create a lead.

The reply path publishes a realtime event too, so an outbound message (human or
AI) lights up every open inbox immediately, same as an inbound one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from one.api.deps import current_principal, db_session
from one.comms.bus import publish_event
from one.comms.models import AuthorKind, Conversation, Message, MessageType
from one.comms.service import mark_read, post_outbound
from one.crm.models import Partner
from one.crm.service import create_lead
from one.identity.security import Principal

router = APIRouter(prefix="/inbox", tags=["inbox"])


class ConversationOut(BaseModel):
    id: str
    partner_name: str | None
    status: str
    unread: int
    last_message_at: int | None


@router.get("/conversations")
async def list_conversations(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
    status: str | None = None,
    limit: int = 50,
) -> list[ConversationOut]:
    q = select(Conversation).order_by(desc(Conversation.last_message_at)).limit(min(limit, 200))
    if status:
        q = q.where(Conversation.status == status)
    convs = (await session.scalars(q)).all()
    partner_ids = {c.partner_id for c in convs if c.partner_id}
    names: dict[uuid.UUID, str] = {}
    if partner_ids:
        for p in (await session.scalars(select(Partner).where(Partner.id.in_(partner_ids)))).all():
            names[p.id] = p.name
    return [
        ConversationOut(
            id=str(c.id),
            partner_name=names.get(c.partner_id) if c.partner_id else None,
            status=c.status.value,
            unread=c.unread_count,
            last_message_at=c.last_message_at,
        )
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
    limit: int = 100,
) -> list[dict]:
    rows = (
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == uuid.UUID(conversation_id))
            .order_by(Message.created_at)
            .limit(min(limit, 500))
        )
    ).all()
    await mark_read(session, conversation_id=conversation_id)
    return [
        {
            "id": str(m.id),
            "direction": m.direction.value,
            "author": m.author_kind.value,
            "type": m.type.value,
            "body": m.body,
            "status": m.status.value,
            "at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


class ReplyIn(BaseModel):
    body: str
    note: bool = False
    channel_id: str | None = None


@router.post("/conversations/{conversation_id}/reply")
async def reply(
    conversation_id: str,
    body: ReplyIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        msg = await post_outbound(
            session,
            conversation_id=conversation_id,
            body=body.body,
            author_kind=AuthorKind.user,
            author_user_id=principal.user_id,
            channel_id=body.channel_id,
            type=MessageType.note if body.note else MessageType.text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await publish_event(
        principal.tenant,
        {"kind": "message.new", "conversation_id": conversation_id, "message_id": str(msg.id)},
    )
    return {"id": str(msg.id), "status": msg.status.value}


class LeadIn(BaseModel):
    name: str
    value: str = "0.00"
    partner_id: str | None = None


@router.post("/conversations/{conversation_id}/lead")
async def lead_from_conversation(
    conversation_id: str,
    body: LeadIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    from decimal import Decimal

    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    lead = await create_lead(
        session,
        name=body.name,
        partner_id=body.partner_id or (str(conv.partner_id) if conv.partner_id else None),
        value=Decimal(body.value),
        source="conversa",
        conversation_id=conversation_id,
        owner_user_id=principal.user_id,
    )
    return {"id": str(lead.id), "name": lead.name}
