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

from one.comms import adapters
from one.comms.bus import GROUP, ensure_group, events_channel, publish_event, stream_key
from one.comms.models import Channel
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


# events_channel re-exported for callers that only import the consumer.
__all__ = ["process_entry", "run_consumer", "drain_once", "events_channel"]
