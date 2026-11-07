"""Stream consumer — drains a tenant's inbound stream into Postgres + events.

This is the worker side of the volume pipeline. It runs in the ``worker`` role
(and can run in many replicas): each reads the consumer group, so the load of a
message burst spreads across them. Processing one entry = resolve the channel's
adapter, persist idempotently, publish a realtime event, ack. A failed entry is
left unacked for retry rather than lost.
"""

from __future__ import annotations

import json
import uuid

import redis.asyncio as redis
from sqlalchemy import select

from one.comms import adapters
from one.comms.bus import (
    GROUP,
    ensure_group,
    events_channel,
    outbound_key,
    publish_event,
    stream_key,
)
from one.comms.models import Channel, Message
from one.comms.outbound import dispatch_message
from one.comms.providers.whatsapp import parse_statuses
from one.comms.service import ingest_inbound
from one.config import get_settings
from one.db.session import tenant_session

_settings = get_settings()


async def process_entry(tenant: str, fields: dict) -> None:
    """Handle one stream entry: {channel: <id>, raw: <json>}."""
    channel_id = fields["channel"]
    raw = json.loads(fields["raw"])
    async with tenant_session(tenant) as session:
        channel = await session.get(Channel, uuid.UUID(channel_id))
        if channel is None:
            return
        for inbound in adapters.parse(channel.type, channel_id, raw):
            conv, message, created = await ingest_inbound(session, inbound)
            if created:
                await publish_event(
                    tenant,
                    {
                        "kind": "message.new",
                        "conversation_id": str(conv.id),
                        "message_id": str(message.id),
                        "channel": channel.type.value,
                        "preview": (message.body or "")[:120],
                        "partner_id": str(conv.partner_id) if conv.partner_id else None,
                        "at": message.created_at.isoformat() if message.created_at else None,
                    },
                )
        # Delivery/read status callbacks arrive in the same webhook shape.
        for st in parse_statuses(raw):
            msg = await session.scalar(
                select(Message).where(
                    Message.channel_id == channel.id,
                    Message.provider_message_id == st["provider_message_id"],
                )
            )
            if msg is not None:
                from one.comms.models import MessageStatus

                msg.status = MessageStatus(st["status"])
                await session.flush()
                await publish_event(
                    tenant,
                    {"kind": "message.status", "message_id": str(msg.id), "status": st["status"]},
                )


async def process_outbound(tenant: str, message_id: str) -> None:
    """Send one queued outbound message via its provider, then publish its status."""
    async with tenant_session(tenant) as session:
        msg = await dispatch_message(session, message_id)
        if msg is not None:
            await publish_event(
                tenant,
                {"kind": "message.status", "message_id": str(msg.id), "status": msg.status.value},
            )


async def run_consumer(tenant: str, consumer_name: str = "w1", block_ms: int = 5000) -> None:
    """Long-running loop: read the group, process, ack. Used by the worker role."""
    r = redis.from_url(_settings.redis_url, decode_responses=True)
    await ensure_group(r, tenant)
    key = stream_key(tenant)
    try:
        while True:
            resp = await r.xreadgroup(GROUP, consumer_name, {key: ">"}, count=32, block=block_ms)
            if not resp:
                continue
            for _stream, entries in resp:
                for entry_id, fields in entries:
                    try:
                        await process_entry(tenant, fields)
                        await r.xack(key, GROUP, entry_id)
                    except Exception:  # noqa: BLE001 - keep the loop alive; entry stays pending
                        continue
    finally:
        await r.aclose()


async def run_outbound_consumer(
    tenant: str, consumer_name: str = "o1", block_ms: int = 5000
) -> None:
    """Long-running loop: drain the outbound stream, sending each message."""
    r = redis.from_url(_settings.redis_url, decode_responses=True)
    await _ensure_group(r, outbound_key(tenant))
    key = outbound_key(tenant)
    try:
        while True:
            resp = await r.xreadgroup(GROUP, consumer_name, {key: ">"}, count=32, block=block_ms)
            if not resp:
                continue
            for _stream, entries in resp:
                for entry_id, fields in entries:
                    try:
                        await process_outbound(tenant, fields["message_id"])
                        await r.xack(key, GROUP, entry_id)
                    except Exception:  # noqa: BLE001
                        continue
    finally:
        await r.aclose()


async def _ensure_group(r, key: str) -> None:
    try:
        await r.xgroup_create(key, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


# Convenience used by the one-shot worker task / tests: drain what's pending now.
async def drain_once(tenant: str, consumer_name: str = "w1") -> int:
    r = redis.from_url(_settings.redis_url, decode_responses=True)
    await ensure_group(r, tenant)
    key = stream_key(tenant)
    processed = 0
    try:
        resp = await r.xreadgroup(GROUP, consumer_name, {key: ">"}, count=128, block=100)
        for _stream, entries in resp or []:
            for entry_id, fields in entries:
                await process_entry(tenant, fields)
                await r.xack(key, GROUP, entry_id)
                processed += 1
    finally:
        await r.aclose()
    return processed


async def drain_outbound_once(tenant: str, consumer_name: str = "o1") -> int:
    r = redis.from_url(_settings.redis_url, decode_responses=True)
    await _ensure_group(r, outbound_key(tenant))
    key = outbound_key(tenant)
    processed = 0
    try:
        resp = await r.xreadgroup(GROUP, consumer_name, {key: ">"}, count=128, block=100)
        for _stream, entries in resp or []:
            for entry_id, fields in entries:
                await process_outbound(tenant, fields["message_id"])
                await r.xack(key, GROUP, entry_id)
                processed += 1
    finally:
        await r.aclose()
    return processed


__all__ = [
    "process_entry",
    "process_outbound",
    "run_consumer",
    "run_outbound_consumer",
    "drain_once",
    "drain_outbound_once",
    "events_channel",
]
