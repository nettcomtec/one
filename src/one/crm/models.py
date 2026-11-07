"""CRM core — partners (contact/company), the sales pipeline and activities.

Partner is the one identity a person or company has across the whole system; the
communication module attaches channel identities and conversations to it, so a
deal carries its full WhatsApp / voice / chat history.

A ``Lead`` here is a *deal* (negócio) in pipeline terms: it lives on a stage,
carries a value and an expected close, and is driven forward by ``Activity``
rows — the "activity-based selling" model the best CRMs (Pipedrive, Close) are
built around. A deal with no scheduled next activity is a deal going cold, and a
deal idle past its stage's ``rotting_days`` is flagged as rotting.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from one.db.base import TenantBase
from one.db.mixins import AuditMixin, PKMixin, SoftDeleteMixin, TimestampMixin


class PartnerKind(enum.StrEnum):
    person = "person"
    company = "company"


class Partner(TenantBase, PKMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "crm_partner"

    kind: Mapped[PartnerKind] = mapped_column(
        Enum(PartnerKind, name="partner_kind"), default=PartnerKind.person, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # CPF (11) or CNPJ (14), digits only.
    doc: Mapped[str | None] = mapped_column(String(14), index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The company this person belongs to (person -> company self-reference).
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_partner.id"), index=True, nullable=True
    )
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Pipeline(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "crm_pipeline"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stages: Mapped[list[Stage]] = relationship(
        back_populates="pipeline", order_by="Stage.sequence", lazy="selectin"
    )


class Stage(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "crm_stage"
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_pipeline.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Default win probability (%) for deals entering this stage — drives forecast.
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Days a deal may sit on this stage before it's flagged as "rotting" (0 = off).
    rotting_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pipeline: Mapped[Pipeline] = relationship(back_populates="stages")


class LeadStatus(enum.StrEnum):
    open = "open"
    won = "won"
    lost = "lost"


class Lead(TenantBase, PKMixin, TimestampMixin, AuditMixin):
    __tablename__ = "crm_lead"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_partner.id"), index=True, nullable=True
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_pipeline.id"), nullable=False
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_stage.id"), index=True, nullable=False
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", native_enum=False, length=8),
        default=LeadStatus.open,
        index=True,
        nullable=False,
    )
    expected_close_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ordering within a kanban column (manual drag order), lower = top.
    board_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Last time anything happened on the deal — stage move or a done activity.
    # Drives the "rotting" / going-cold signal.
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Where this lead came from, when it originated in a conversation.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_conversation.id"), nullable=True
    )


class ActivityKind(enum.StrEnum):
    task = "task"
    call = "call"
    meeting = "meeting"
    email = "email"
    whatsapp = "whatsapp"
    deadline = "deadline"
    note = "note"


class Activity(TenantBase, PKMixin, TimestampMixin, AuditMixin):
    """A planned or logged touch on a deal/contact — the CRM's heartbeat.

    Open activities with a ``due_at`` are the agenda; ``done`` ones are the
    timeline. A deal's "next activity" is its earliest open activity.
    """

    __tablename__ = "crm_activity"

    kind: Mapped[ActivityKind] = mapped_column(
        Enum(ActivityKind, name="activity_kind"), default=ActivityKind.task, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    done: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("crm_lead.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_partner.id"), index=True, nullable=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class LostReason(TenantBase, PKMixin, TimestampMixin):
    """Curated list of why deals are lost — powers win/loss analysis."""

    __tablename__ = "crm_lost_reason"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
