"""Outbound dispatch — send a queued message through its channel's provider.

The reply path only persists a message as ``queued`` and enqueues its id; this
runs in the worker and does the actual provider call, so a slow or failing Meta
request never blocks the agent's request. On success it records the provider's
message id (for status callbacks) and flips the message to ``sent``; on failure
it marks ``failed``. Non-WhatsApp channels (webchat/internal) have no external
leg and are marked ``sent`` immediately.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from one.comms.models import (
    Channel,
    ChannelType,
    ContactIdentity,
    Conversation,
    Message,
    MessageStatus,
    MessageType,
)
from one.comms.providers.whatsapp import WhatsAppClient, WhatsAppError


async def _recipient_address(
    session: AsyncSession, message: Message, channel: Channel
) -> str | None:
    """The address to send to: the partner's identity on this channel."""
    conv = await session.get(Conversation, message.conversation_id)
    if conv is None or conv.partner_id is None:
        return None
    idn = await session.scalar(
        select(ContactIdentity).where(
            ContactIdentity.partner_id == conv.partner_id,
            ContactIdentity.channel_type == channel.type,
        )
    )
    return idn.address if idn else None


async def dispatch_message(session: AsyncSession, message_id: str) -> Message | None:
    """Send one queued message through its channel. Returns the updated message."""
    message = await session.get(Message, uuid.UUID(message_id))
    if message is None or message.status != MessageStatus.queued:
        return message
    channel = await session.get(Channel, message.channel_id)
    if channel is None:
        message.status = MessageStatus.failed
        await session.flush()
        return message

    if channel.type != ChannelType.whatsapp:
        # Webchat / internal: nothing to call out to.
        message.status = MessageStatus.sent
        await session.flush()
        return message

    cfg = channel.config or {}
    to = await _recipient_address(session, message, channel)
    if (
        not to
        or not cfg.get("access_token")
        or not (cfg.get("phone_number_id") or channel.external_id)
    ):
        message.status = MessageStatus.failed
        message.payload = {
            **(message.payload or {}),
            "error": "canal WhatsApp sem credenciais ou destinatário",
        }
        await session.flush()
        return message

    client = WhatsAppClient(
        access_token=cfg["access_token"],
        phone_number_id=cfg.get("phone_number_id") or channel.external_id,
    )
    try:
        if message.type == MessageType.template:
            tmpl = (message.payload or {}).get("template", {})
            pid = await client.send_template(
                to=to,
                name=tmpl.get("name", ""),
                language=tmpl.get("language", "pt_BR"),
                components=tmpl.get("components"),
            )
        else:
            pid = await client.send_text(to=to, body=message.body or "")
        message.provider_message_id = pid
        message.status = MessageStatus.sent
    except WhatsAppError as exc:
        message.status = MessageStatus.failed
        message.payload = {**(message.payload or {}), "error": str(exc)}
    await session.flush()
    return message
