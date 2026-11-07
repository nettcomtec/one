"""Communication services — the only sanctioned way to write the inbox.

These functions are transport-agnostic: a webhook worker, the REST inbox and the
AI agent all go through them, so idempotency, conversation resolution and the
unread/last-message bookkeeping live in exactly one place.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from one.comms.models import (
    AuthorKind,
    Channel,
    ContactIdentity,
    Conversation,
    ConversationStatus,
    Direction,
    Message,
    MessageStatus,
    MessageType,
)
from one.crm.models import Partner, PartnerKind


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class InboundMessage:
    """Normalized shape every channel adapter produces from a provider payload."""

    channel_id: str
    address: str  # sender address on the channel (phone, @handle, session id)
    provider_message_id: str | None = None
    type: MessageType = MessageType.text
    body: str | None = None
    payload: dict = field(default_factory=dict)
    display_name: str | None = None


async def _resolve_partner(
    session: AsyncSession, *, channel_type, address, display_name
) -> Partner:
    ident = await session.scalar(
        select(ContactIdentity).where(
            ContactIdentity.channel_type == channel_type,
            ContactIdentity.address == address,
        )
    )
    if ident is not None:
        partner = await session.get(Partner, ident.partner_id)
        if partner is not None:
            return partner
    partner = Partner(kind=PartnerKind.person, name=display_name or address)
    session.add(partner)
    await session.flush()
    session.add(ContactIdentity(partner_id=partner.id, channel_type=channel_type, address=address))
    await session.flush()
    return partner


async def _open_conversation(
    session: AsyncSession, *, partner_id, channel: Channel
) -> Conversation:
    conv = await session.scalar(
        select(Conversation).where(
            Conversation.partner_id == partner_id,
            Conversation.primary_channel_id == channel.id,
            Conversation.status != ConversationStatus.resolved,
        )
    )
    if conv is not None:
        return conv
    conv = Conversation(partner_id=partner_id, primary_channel_id=channel.id)
    session.add(conv)
    await session.flush()
    return conv


async def ingest_inbound(
    session: AsyncSession, msg: InboundMessage
) -> tuple[Conversation, Message, bool]:
    """Persist an inbound message idempotently.

    Returns ``(conversation, message, created)``. ``created`` is False when the
    provider message was already stored (a duplicate webhook delivery).
    """
    channel = await session.get(Channel, uuid.UUID(msg.channel_id))
    if channel is None:
        raise ValueError(f"Unknown channel {msg.channel_id}")

    # Idempotency: same (channel, provider_message_id) is a duplicate delivery.
    if msg.provider_message_id:
        existing = await session.scalar(
            select(Message).where(
                Message.channel_id == channel.id,
                Message.provider_message_id == msg.provider_message_id,
            )
        )
        if existing is not None:
            conv = await session.get(Conversation, existing.conversation_id)
            return conv, existing, False

    partner = await _resolve_partner(
        session, channel_type=channel.type, address=msg.address, display_name=msg.display_name
    )
    conv = await _open_conversation(session, partner_id=partner.id, channel=channel)

    message = Message(
        conversation_id=conv.id,
        channel_id=channel.id,
        direction=Direction.inbound,
        author_kind=AuthorKind.contact,
        type=msg.type,
        body=msg.body,
        payload=msg.payload,
        provider_message_id=msg.provider_message_id,
        status=MessageStatus.received,
    )
    session.add(message)
    ts = now_ms()
    conv.last_message_at = ts
    conv.last_inbound_at = ts  # resets the WhatsApp 24h window
    conv.unread_count = conv.unread_count + 1
    if conv.status == ConversationStatus.resolved:
        conv.status = ConversationStatus.open
    await session.flush()
    return conv, message, True


WINDOW_MS = 24 * 60 * 60 * 1000  # WhatsApp customer-service window: 24 hours


def within_24h_window(last_inbound_at: int | None, *, at: int | None = None) -> bool:
    """True when a free-form message may still be sent (inside 24h of last inbound)."""
    if last_inbound_at is None:
        return False
    return (at or now_ms()) - last_inbound_at < WINDOW_MS


class WindowClosedError(ValueError):
    """Raised when a free-form WhatsApp message is attempted outside the 24h window."""


async def post_outbound(
    session: AsyncSession,
    *,
    conversation_id: str,
    body: str,
    author_kind: AuthorKind = AuthorKind.user,
    author_user_id: str | None = None,
    channel_id: str | None = None,
    type: MessageType = MessageType.text,
) -> Message:
    """Queue an outbound message (a human, or the AI agent, replying).

    ``channel_id`` defaults to the conversation's primary channel; passing a
    different one is how a hybrid conversation injects another transport.
    A ``type=note`` message is internal and never sent to the customer.
    On WhatsApp, a free-form (non-template) message outside the 24h window is
    refused with ``WindowClosedError`` — Meta only allows templates there.
    """
    from one.comms.models import Channel, ChannelType

    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if conv is None:
        raise ValueError("Unknown conversation")
    ch_id = uuid.UUID(channel_id) if channel_id else conv.primary_channel_id
    is_note = type == MessageType.note

    if not is_note and type != MessageType.template:
        channel = await session.get(Channel, ch_id)
        if (
            channel is not None
            and channel.type == ChannelType.whatsapp
            and not within_24h_window(conv.last_inbound_at)
        ):
            raise WindowClosedError(
                "Janela de 24h encerrada. Envie um template aprovado para retomar."
            )
    message = Message(
        conversation_id=conv.id,
        channel_id=ch_id,
        direction=Direction.outbound,
        author_kind=author_kind,
        author_user_id=uuid.UUID(author_user_id) if author_user_id else None,
        type=type,
        body=body,
        status=MessageStatus.sent if is_note else MessageStatus.queued,
    )
    session.add(message)
    conv.last_message_at = now_ms()
    if not is_note:
        conv.unread_count = 0  # replying clears the unread badge
    await session.flush()
    return message


async def mark_read(session: AsyncSession, *, conversation_id: str) -> None:
    conv = await session.get(Conversation, uuid.UUID(conversation_id))
    if conv is not None:
        conv.unread_count = 0
        await session.flush()
