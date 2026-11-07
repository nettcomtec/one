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
from one.comms.bus import enqueue_outbound, publish_event
from one.comms.models import (
    AuthorKind,
    Channel,
    ContactIdentity,
    Conversation,
    ConversationLabel,
    Label,
    Message,
    MessageStatus,
    MessageType,
)
from one.comms.service import WindowClosedError, mark_read, post_outbound, within_24h_window
from one.crm.models import Lead, Partner, Stage
from one.crm.service import create_lead
from one.desk.models import Ticket, TicketPriority, TicketStatus
from one.desk.service import create_ticket, set_status
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
    except WindowClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()  # make the message visible to the outbound worker
    if msg.status == MessageStatus.queued:
        await enqueue_outbound(principal.tenant, str(msg.id))
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


# --------------------------------------------------------------------------- context panel
@router.get("/conversations/{conversation_id}/context")
async def conversation_context(
    conversation_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Everything the right-hand panel shows: contact, channels, linked lead/ticket, 24h window."""
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    channel = await session.get(Channel, conv.primary_channel_id)

    partner = await session.get(Partner, conv.partner_id) if conv.partner_id else None
    identities: list[dict] = []
    if conv.partner_id:
        for idn in (
            await session.scalars(
                select(ContactIdentity).where(ContactIdentity.partner_id == conv.partner_id)
            )
        ).all():
            identities.append({"channel_type": idn.channel_type.value, "address": idn.address})

    # labels on this conversation
    tags = []
    rows = (
        await session.scalars(
            select(Label)
            .join(ConversationLabel, ConversationLabel.label_id == Label.id)
            .where(ConversationLabel.conversation_id == conv.id)
        )
    ).all()
    for lbl in rows:
        tags.append({"name": lbl.name, "color": lbl.color})

    # linked leads
    leads = []
    for ld in (await session.scalars(select(Lead).where(Lead.conversation_id == conv.id))).all():
        stage = await session.get(Stage, ld.stage_id)
        leads.append(
            {
                "id": str(ld.id),
                "name": ld.name,
                "value": f"{ld.value:.2f}",
                "stage": stage.name if stage else None,
            }
        )

    # linked tickets
    tickets = []
    for tk in (
        await session.scalars(select(Ticket).where(Ticket.conversation_id == conv.id))
    ).all():
        tickets.append(
            {
                "id": str(tk.id),
                "number": tk.number,
                "subject": tk.subject,
                "status": tk.status.value,
                "priority": tk.priority.value,
                "sla_state": tk.sla_state.value,
                "sla_due_at": tk.sla_due_at,
            }
        )

    return {
        "conversation": {"id": str(conv.id), "status": conv.status.value},
        "channel": {"type": channel.type.value, "name": channel.name} if channel else None,
        "partner": (
            {
                "id": str(partner.id),
                "name": partner.name,
                "trade_name": partner.trade_name,
                "doc": partner.doc,
            }
            if partner
            else None
        ),
        "identities": identities,
        "tags": tags,
        "window": {
            "open": within_24h_window(conv.last_inbound_at),
            "last_inbound_at": conv.last_inbound_at,
        },
        "leads": leads,
        "tickets": tickets,
    }


# --------------------------------------------------------------------------- tickets
class TicketIn(BaseModel):
    subject: str
    priority: str = "normal"


@router.post("/conversations/{conversation_id}/ticket")
async def ticket_from_conversation(
    conversation_id: str,
    body: TicketIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    try:
        prio = TicketPriority(body.priority)
    except ValueError:
        prio = TicketPriority.normal
    ticket = await create_ticket(
        session,
        subject=body.subject,
        partner_id=str(conv.partner_id) if conv.partner_id else None,
        conversation_id=conversation_id,
        priority=prio,
    )
    return {"id": str(ticket.id), "number": ticket.number}


@router.get("/conversations/{conversation_id}/templates")
async def list_templates(
    conversation_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    """Approved WhatsApp templates available on this conversation's channel."""
    from one.comms.models import WaTemplate, WaTemplateStatus

    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    rows = (
        await session.scalars(
            select(WaTemplate).where(
                WaTemplate.channel_id == conv.primary_channel_id,
                WaTemplate.status == WaTemplateStatus.approved,
            )
        )
    ).all()
    return [{"id": str(t.id), "name": t.name, "language": t.language, "body": t.body} for t in rows]


class TemplateIn(BaseModel):
    template_id: str


@router.post("/conversations/{conversation_id}/template")
async def send_template(
    conversation_id: str,
    body: TemplateIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Send an approved template — the only message allowed outside the 24h window."""
    from one.comms.models import WaTemplate

    tmpl = await session.get(WaTemplate, uuid.UUID(body.template_id))
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    msg = await post_outbound(
        session,
        conversation_id=conversation_id,
        body=tmpl.body,
        author_kind=AuthorKind.user,
        author_user_id=principal.user_id,
        type=MessageType.template,
    )
    msg.payload = {"template": {"name": tmpl.name, "language": tmpl.language}}
    await session.flush()
    await session.commit()
    if msg.status == MessageStatus.queued:
        await enqueue_outbound(principal.tenant, str(msg.id))
    await publish_event(
        principal.tenant,
        {"kind": "message.new", "conversation_id": conversation_id, "message_id": str(msg.id)},
    )
    return {"id": str(msg.id), "status": msg.status.value}


class TicketPatch(BaseModel):
    status: str | None = None
    priority: str | None = None


@router.patch("/tickets/{ticket_id}")
async def patch_ticket(
    ticket_id: str,
    body: TicketPatch,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    ticket = await session.get(Ticket, uuid.UUID(ticket_id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    if body.priority:
        try:
            ticket.priority = TicketPriority(body.priority)
        except ValueError:
            pass
    if body.status:
        try:
            await set_status(session, ticket_id=ticket_id, status=TicketStatus(body.status))
        except ValueError:
            pass
    await session.flush()
    return {"id": str(ticket.id), "status": ticket.status.value, "priority": ticket.priority.value}
