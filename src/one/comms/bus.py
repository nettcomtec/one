"""Realtime message bus — Redis Streams for ingestion, pub/sub for delivery.

Two distinct jobs, deliberately separated:

* **Ingestion** uses a Redis *Stream* (``XADD`` + a consumer group). Streams give
  durability, ordering and at-least-once delivery, and let many worker replicas
  consume in parallel — this is what absorbs a burst of simultaneous messages
  without dropping any or overrunning Postgres.
* **Delivery** to connected agents uses Redis *pub/sub*. After a worker persists
  a message it publishes a small event; every gateway replica holding a relevant
  WebSocket forwards it. Pub/sub is fire-and-forget, which is right for live UI.

The stream key and channel are namespaced per tenant so one client's firehose
never touches another's.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import redis.asyncio as redis

from one.config import get_settings

_settings = get_settings()
GROUP = "workers"
STREAM_MAXLEN = 50_000  # cap the stream; persisted rows are the source of truth


def _client() -> redis.Redis:
    return redis.from_url(_settings.redis_url, decode_responses=True)


def stream_key(tenant: str) -> str:
    return f"one:{tenant}:inbound"


def outbound_key(tenant: str) -> str:
    return f"one:{tenant}:outbound"


def events_channel(tenant: str) -> str:
    return f"one:{tenant}:events"


async def enqueue_inbound(tenant: str, channel: str, raw: dict) -> str:
    """Append a raw inbound payload to the tenant's ingestion stream (fast path)."""
    r = _client()
    try:
        return await r.xadd(
            stream_key(tenant),
            {"channel": channel, "raw": json.dumps(raw)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    finally:
        await r.aclose()


async def enqueue_outbound(tenant: str, message_id: str) -> str:
    """Append a queued message id to the tenant's outbound stream (worker sends it)."""
    r = _client()
    try:
        return await r.xadd(
            outbound_key(tenant),
            {"message_id": message_id},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    finally:
        await r.aclose()


async def publish_event(tenant: str, event: dict) -> None:
    """Publish a realtime event (new message, status change) to the tenant channel."""
    r = _client()
    try:
        await r.publish(events_channel(tenant), json.dumps(event))
    finally:
        await r.aclose()


async def ensure_group(r: redis.Redis, tenant: str) -> None:
    try:
        await r.xgroup_create(stream_key(tenant), GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def subscribe_events(tenant: str) -> AsyncIterator[dict]:
    """Yield realtime events for a tenant until the caller stops iterating."""
    r = _client()
    pubsub = r.pubsub()
    await pubsub.subscribe(events_channel(tenant))
    try:
        async for msg in pubsub.listen():
            if msg.get("type") == "message":
                try:
                    yield json.loads(msg["data"])
                except (ValueError, TypeError):
                    continue
    finally:
        await pubsub.unsubscribe(events_channel(tenant))
        await pubsub.aclose()
        await r.aclose()
