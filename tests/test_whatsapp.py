"""WhatsApp (Meta) outbound, 24h window and status callbacks — no real network."""

from __future__ import annotations

import json
import os

import httpx
import pytest

requires_db = pytest.mark.skipif(
    not os.environ.get("ONE_TEST_DATABASE_URL"), reason="ONE_TEST_DATABASE_URL not set"
)


def _mock_client(captured: list) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.SENT1"}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_client_send_text_builds_payload_and_returns_id():
    from one.comms.providers.whatsapp import WhatsAppClient

    captured: list = []
    client = WhatsAppClient(access_token="t", phone_number_id="123", client=_mock_client(captured))
    pid = await client.send_text(to="5551999", body="Olá!")
    assert pid == "wamid.SENT1"
    assert captured[0]["type"] == "text" and captured[0]["text"]["body"] == "Olá!"
    assert captured[0]["to"] == "5551999"


def test_signature_verification():
    import hashlib
    import hmac

    from one.comms.providers.whatsapp import verify_signature

    secret, body = "s3cr3t", b'{"a":1}'
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, good) is True
    assert verify_signature(secret, body, "sha256=deadbeef") is False
    assert verify_signature(secret, body, None) is False


def test_parse_statuses():
    from one.comms.providers.whatsapp import parse_statuses

    raw = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.X", "status": "delivered"},
                                {"id": "wamid.Y", "status": "read"},
                            ]
                        }
                    }
                ]
            }
        ]
    }
    out = parse_statuses(raw)
    assert {"provider_message_id": "wamid.X", "status": "delivered"} in out
    assert {"provider_message_id": "wamid.Y", "status": "read"} in out


@requires_db
async def test_window_closed_blocks_free_text(provisioned_tenant):
    from sqlalchemy import update

    from one.comms.models import Channel, ChannelType, Conversation
    from one.comms.service import InboundMessage, WindowClosedError, ingest_inbound, post_outbound
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        ch = Channel(type=ChannelType.whatsapp, name="wa", external_id="p")
        session.add(ch)
        await session.flush()
        conv, _m, _c = await ingest_inbound(
            session,
            InboundMessage(
                channel_id=str(ch.id), address="5551", body="oi", provider_message_id="i1"
            ),
        )
        # force the window shut (last inbound 48h ago)
        await session.execute(
            update(Conversation).where(Conversation.id == conv.id).values(last_inbound_at=1)
        )
        await session.flush()
        with pytest.raises(WindowClosedError):
            await post_outbound(session, conversation_id=str(conv.id), body="oportunidade")


@requires_db
async def test_dispatch_sends_whatsapp_and_sets_status(provisioned_tenant, monkeypatch):
    from one.comms import outbound as outbound_mod
    from one.comms.models import (
        Channel,
        ChannelType,
        MessageStatus,
    )
    from one.comms.service import InboundMessage, ingest_inbound, post_outbound
    from one.db.session import tenant_session

    captured: list = []

    # Patch the client factory used inside dispatch to our mock transport.
    from one.comms.providers import whatsapp as wa_mod

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
        msg = await post_outbound(session, conversation_id=str(conv.id), body="Oi de volta!")
        assert msg.status == MessageStatus.queued
        sent = await outbound_mod.dispatch_message(session, str(msg.id))
        assert sent.status == MessageStatus.sent
        assert sent.provider_message_id == "wamid.SENT1"
        assert captured and captured[0]["text"]["body"] == "Oi de volta!"
