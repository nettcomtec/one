"""Outbound roundtrip: reply queues → outbound stream → worker sends → status.

Needs Postgres + Redis (CI provides both).
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

_DB = os.environ.get("ONE_TEST_DATABASE_URL")
_REDIS = os.environ.get("ONE_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    not (_DB and _REDIS), reason="needs ONE_TEST_DATABASE_URL and ONE_TEST_REDIS_URL"
)
if _REDIS:
    os.environ["ONE_REDIS_URL"] = _REDIS


def _mock_client(captured: list) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT"}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_reply_then_worker_sends(provisioned_tenant, monkeypatch):
    from one.comms.bus import enqueue_outbound
    from one.comms.consumer import drain_outbound_once
    from one.comms.models import Channel, ChannelType, MessageStatus
    from one.comms.providers import whatsapp as wa_mod
    from one.comms.service import InboundMessage, ingest_inbound, post_outbound
    from one.db.session import tenant_session

    captured: list = []
    real_init = wa_mod.WhatsAppClient.__init__

    def fake_init(self, *, access_token, phone_number_id, client=None):
        real_init(
            self,
            access_token=access_token,
            phone_number_id=phone_number_id,
            client=_mock_client(captured),
        )

    monkeypatch.setattr(wa_mod.WhatsAppClient, "__init__", fake_init)

    async with tenant_session(provisioned_tenant) as session:
        ch = Channel(
            type=ChannelType.whatsapp,
            name="wa",
            external_id="123",
            config={"access_token": "t", "phone_number_id": "123"},
        )
        session.add(ch)
        await session.flush()
        conv, _m, _c = await ingest_inbound(
            session,
            InboundMessage(
                channel_id=str(ch.id), address="5551999", body="oi", provider_message_id="i1"
            ),
        )
        msg = await post_outbound(
            session, conversation_id=str(conv.id), body="Resposta do atendente"
        )
        mid = str(msg.id)
    # enqueue + worker sends (separate session, like production)
    await enqueue_outbound(provisioned_tenant, mid)
    processed = await drain_outbound_once(provisioned_tenant)
    assert processed == 1

    from sqlalchemy import select

    from one.comms.models import Message
    from one.db.session import tenant_session as ts2

    async with ts2(provisioned_tenant) as session:
        sent = await session.scalar(
            select(Message).where(Message.id == __import__("uuid").UUID(mid))
        )
        assert sent.status == MessageStatus.sent
        assert sent.provider_message_id == "wamid.OUT"
    assert captured and captured[0]["text"]["body"] == "Resposta do atendente"
