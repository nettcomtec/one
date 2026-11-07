"""Help Desk — tickets with SLA, linkable to a conversation and a partner.

A ticket is the unit of support work. Unlike the Fullchat setup where tickets
live in a separate Odoo linked by reference, here the ticket is native in the
same database as the conversation, lead and billing, so a single query joins
them and the AI agent can open/update one as a first-class action.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from one.db.base import TenantBase
from one.db.mixins import AuditMixin, PKMixin, TimestampMixin


class TicketStatus(enum.StrEnum):
    open = "open"
    pending = "pending"
    on_hold = "on_hold"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(enum.StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class SlaState(enum.StrEnum):
    running = "running"
    paused = "paused"
    met = "met"
    breached = "breached"


class Team(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "desk_team"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Default first-response SLA target in minutes.
    sla_first_response_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)


class Ticket(TenantBase, PKMixin, TimestampMixin, AuditMixin):
    __tablename__ = "desk_ticket"

    # Human-facing sequential number (filled from a sequence on create).
    number: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"), default=TicketStatus.open, nullable=False
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority"), default=TicketPriority.normal, nullable=False
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_partner.id"), index=True, nullable=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_conversation.id"), index=True, nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("desk_team.id"), nullable=True
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    # SLA tracking (epoch ms, like the conversation's last_message_at).
    sla_state: Mapped[SlaState] = mapped_column(
        Enum(SlaState, name="sla_state"), default=SlaState.running, nullable=False
    )
    sla_due_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    first_responded_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
