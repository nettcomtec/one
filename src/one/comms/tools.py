"""Comms actions exposed as AI tools — the agent operates the inbox like a user.

Same service layer, same permission gate as the REST inbox, so the agent can
reply, leave an internal note, resolve a conversation, or turn one into a lead,
and every one of those shows up live in the agents' inboxes."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from one.ai.registry import ToolContext, tool
from one.comms.bus import publish_event
from one.comms.models import AuthorKind, MessageType
from one.comms.service import post_outbound
from one.crm.service import create_lead


class ReplyIn(BaseModel):
    conversation_id: str
    body: str = Field(min_length=1)
    note: bool = Field(default=False, description="Internal note, not sent to the customer")


@tool(
    "comms.reply",
    permission="comms.reply",
    description="Reply in a conversation (or leave an internal note) as the AI agent.",
)
async def comms_reply(ctx: ToolContext, args: ReplyIn) -> dict:
    msg = await post_outbound(
        ctx.session,
        conversation_id=args.conversation_id,
        body=args.body,
        author_kind=AuthorKind.ai,
        type=MessageType.note if args.note else MessageType.text,
    )
    await publish_event(
        ctx.tenant,
        {"kind": "message.new", "conversation_id": args.conversation_id, "message_id": str(msg.id)},
    )
    return {"id": str(msg.id), "status": msg.status.value}


class LeadIn(BaseModel):
    name: str
    value: str = "0.00"
    conversation_id: str | None = None
    partner_id: str | None = None


@tool(
    "crm.create_lead",
    permission="crm.lead.create",
    description="Create a CRM lead, optionally from a conversation.",
)
async def crm_create_lead(ctx: ToolContext, args: LeadIn) -> dict:
    lead = await create_lead(
        ctx.session,
        name=args.name,
        value=Decimal(args.value),
        conversation_id=args.conversation_id,
        partner_id=args.partner_id,
        source="agente",
    )
    return {"id": str(lead.id), "name": lead.name}
