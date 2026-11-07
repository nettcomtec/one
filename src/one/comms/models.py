"""Communication core — omnichannel inbox, channel-agnostic.

Design notes baked into the schema:

* A ``Channel`` is one configured connection (a WhatsApp number, a webchat
  widget, a VoIP trunk, an Instagram account, an email box). Adding a new kind
  of channel is a new adapter, not a schema change.
* A person is a ``crm.Partner``; ``ContactIdentity`` maps that partner to an
  address on a channel (phone E.164 for WhatsApp, a SIP/number for VoIP, a
  webchat session id, an @handle), so every channel converges on one partner.
* A ``Conversation`` is anchored to a PRIMARY channel, but each ``Message``
  carries its OWN ``channel_id`` (its real transport). That is what makes a
  conversation *hybrid*: a live webchat can be injected into a WhatsApp thread,
  and internal notes (author=user, type=note) live alongside customer messages.
* ``Message`` is the high-volume table: indexed by (conversation, time) and
  deduplicated by (channel, provider_message_id). Written by workers off a
  Redis stream, never inside the request that received the webhook.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from one.db.base import TenantBase
from one.db.mixins import PKMixin, TimestampMixin


class ChannelType(enum.StrEnum):
    whatsapp = "whatsapp"
    webchat = "webchat"
    instagram = "instagram"
    messenger = "messenger"
    voip = "voip"
    email = "email"
    sms = "sms"
    internal = "internal"  # notes / injected live chat


class ChannelStatus(enum.StrEnum):
    active = "active"
    paused = "paused"
    error = "error"


class ConversationStatus(enum.StrEnum):
    open = "open"
    pending = "pending"
    snoozed = "snoozed"
    resolved = "resolved"


class Direction(enum.StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class AuthorKind(enum.StrEnum):
    contact = "contact"  # the customer
    user = "user"  # a human agent
    ai = "ai"  # the AI agent
    system = "system"  # automated/system event


class MessageType(enum.StrEnum):
    text = "text"
    image = "image"
    audio = "audio"
    video = "video"
    file = "file"
    location = "location"
    template = "template"  # WhatsApp HSM, etc.
    call = "call"  # VoIP call event
    note = "note"  # internal note (not sent to the customer)


class MessageStatus(enum.StrEnum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"
    received = "received"  # inbound


class Channel(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "comm_channel"
    type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Provider-side id (phone number id, page id, trunk, inbox id).
    external_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus, name="channel_status"), default=ChannelStatus.active, nullable=False
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class ContactIdentity(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "comm_identity"
    partner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("crm_partner.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type"), nullable=False
    )
    # Address on that channel: phone E.164, @handle, email, webchat session, SIP.
    address: Mapped[str] = mapped_column(String(320), nullable=False)
    __table_args__ = (UniqueConstraint("channel_type", "address", name="identity_channel_address"),)


class Conversation(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "comm_conversation"
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("crm_partner.id"), index=True, nullable=True
    )
    # The channel the thread is anchored to; individual messages may use another.
    primary_channel_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_channel.id"), nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status"),
        default=ConversationStatus.open,
        nullable=False,
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), index=True, nullable=True
    )
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Mirror of the newest message time, for cheap inbox ordering.
    last_message_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Newest INBOUND message time (epoch ms) — drives the WhatsApp 24h window:
    # outside 24h of this, only an approved template may be sent.
    last_inbound_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", order_by="Message.created_at", lazy="raise_on_sql"
    )
    __table_args__ = (Index("ix_conversation_inbox", "status", "last_message_at"),)


class Message(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "comm_message"
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_conversation.id", ondelete="CASCADE"), nullable=False
    )
    # The REAL transport of this message — may differ from the conversation's
    # primary channel. This is the hybrid-conversation hinge.
    channel_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_channel.id"), nullable=False
    )
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, name="msg_direction"), nullable=False
    )
    author_kind: Mapped[AuthorKind] = mapped_column(
        Enum(AuthorKind, name="author_kind"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type"), default=MessageType.text, nullable=False
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Provider's id for this message — unique per channel for idempotency.
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status"), default=MessageStatus.received, nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_message_conv_time", "conversation_id", "created_at"),
        Index(
            "uq_message_provider",
            "channel_id",
            "provider_message_id",
            unique=True,
            postgresql_where=text("provider_message_id IS NOT NULL"),
        ),
    )


class Label(TenantBase, PKMixin, TimestampMixin):
    """A colored tag an agent puts on conversations (convênio, quente, …)."""

    __tablename__ = "comm_label"
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#3B5BDB", nullable=False)


class ConversationLabel(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "comm_conversation_label"
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_conversation.id", ondelete="CASCADE"), nullable=False
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_label.id", ondelete="CASCADE"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("conversation_id", "label_id", name="uq_conversation_label"),
    )


class CannedResponse(TenantBase, PKMixin, TimestampMixin):
    """A reusable reply an agent inserts by its shortcut (e.g. /horarios)."""

    __tablename__ = "comm_canned"
    shortcut: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class WaTemplateStatus(enum.StrEnum):
    approved = "approved"
    pending = "pending"
    rejected = "rejected"


class WaTemplate(TenantBase, PKMixin, TimestampMixin):
    """A WhatsApp (Meta) message template — the only thing sendable after 24h."""

    __tablename__ = "comm_wa_template"
    channel_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comm_channel.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(12), default="pt_BR", nullable=False)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[WaTemplateStatus] = mapped_column(
        Enum(WaTemplateStatus, name="wa_template_status"),
        default=WaTemplateStatus.pending,
        nullable=False,
    )
    # The template body with {{1}} placeholders, as approved by Meta.
    body: Mapped[str] = mapped_column(Text, nullable=False)
