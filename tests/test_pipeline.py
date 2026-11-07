"""End-to-end volume pipeline: enqueue → stream → worker drains → event published.

Needs both Postgres (ONE_TEST_DATABASE_URL) and Redis (ONE_TEST_REDIS_URL).
"""

from __future__ import annotations

import asyncio
import os

import pytest

_DB = os.environ.get("ONE_TEST_DATABASE_URL")
_REDIS = os.environ.get("ONE_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    not (_DB and _REDIS), reason="needs ONE_TEST_DATABASE_URL and ONE_TEST_REDIS_URL"
)

if _REDIS:
    os.environ["ONE_REDIS_URL"] = _REDIS


async def test_webhook_to_event_roundtrip(provisioned_tenant):
    import redis.asyncio as redis

    from one.comms.bus import enqueue_inbound, events_channel, stream_key
    from one.comms.consumer import drain_once
    from one.comms.models import Channel, ChannelType
    from one.db.session import tenant_session

    tenant = provisioned_tenant

    # a channel to receive on
    async with tenant_session(tenant) as session:
        ch = Channel(type=ChannelType.whatsapp, name="wa", external_id="x")
        session.add(ch)
        await session.flush()
        channel_id = str(ch.id)

    # subscribe to the realtime events channel before draining
    r = redis.from_url(_REDIS, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(events_channel(tenant))
    await asyncio.sleep(0.1)

    # provider posts an inbound WhatsApp payload → webhook would enqueue this:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "5551234", "profile": {"name": "Cliente"}}],
                            "messages": [
                                {
                                    "from": "5551234",
                                    "id": "wamid.RT",
                                    "type": "text",
                                    "text": {"body": "Olá!"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    await enqueue_inbound(tenant, channel_id, payload)

    # worker drains the stream → persists + publishes
    processed = await drain_once(tenant)
    assert processed == 1

    # the realtime event reached the subscriber (what the gateway would forward)
    got = None
    for _ in range(20):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if msg and msg.get("type") == "message":
            got = msg["data"]
            break
    await pubsub.unsubscribe(events_channel(tenant))
    await pubsub.aclose()

    # and the message is durably stored
    from sqlalchemy import select

    from one.comms.models import Message
    from one.db.session import tenant_session as ts2

    async with ts2(tenant) as session:
        stored = (await session.scalars(select(Message))).all()

    # cleanup the stream key
    r2 = redis.from_url(_REDIS, decode_responses=True)
    await r2.delete(stream_key(tenant))
    await r2.aclose()
    await r.aclose()

    assert got is not None and "message.new" in got
    assert len(stored) == 1 and stored[0].body == "Olá!"
