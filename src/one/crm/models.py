"""CRM core — the partner (contact/company) and the sales pipeline.

Partner is the one identity a person or company has across the whole system; the
communication module attaches channel identities and conversations to it, so a
lead carries its full WhatsApp / voice / chat history.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
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
    pipeline: Mapped[Pipeline] = relationship(back_populates="stages")


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
    # Where this lead came from, when it originated in a conversation.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_conversation.id"), nullable=True
    )
