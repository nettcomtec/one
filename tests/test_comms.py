"""Communication core — idempotent ingest, hybrid messages, lead from conversation.

DB-backed; skipped unless ONE_TEST_DATABASE_URL is set (CI provides one).
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ONE_TEST_DATABASE_URL"), reason="ONE_TEST_DATABASE_URL not set"
)


async def _make_channel(session, ctype="whatsapp"):
    from one.comms.models import Channel, ChannelType

    ch = Channel(type=ChannelType(ctype), name=f"{ctype} test", external_id="x")
    session.add(ch)
    await session.flush()
    return ch


async def test_ingest_is_idempotent(provisioned_tenant):
    from one.comms.service import InboundMessage, ingest_inbound
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        ch = await _make_channel(session)
        msg = InboundMessage(
            channel_id=str(ch.id), address="5551999", provider_message_id="wamid.1", body="Oi"
        )
        conv1, m1, created1 = await ingest_inbound(session, msg)
        conv2, m2, created2 = await ingest_inbound(session, msg)  # duplicate delivery

    assert created1 is True and created2 is False
    assert m1.id == m2.id and conv1.id == conv2.id


async def test_ingest_unifies_contact_and_counts_unread(provisioned_tenant):
    from sqlalchemy import select

    from one.comms.models import Conversation
    from one.comms.service import InboundMessage, ingest_inbound
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        ch = await _make_channel(session)
        addr = "5551888"
        await ingest_inbound(session, InboundMessage(channel_id=str(ch.id), address=addr, body="1", provider_message_id="a"))
        conv, _m, _c = await ingest_inbound(
            session, InboundMessage(channel_id=str(ch.id), address=addr, body="2", provider_message_id="b")
        )
        # same address → same partner → same open conversation, unread=2
        convs = (await session.scalars(select(Conversation))).all()

    assert len(convs) == 1
    assert conv.unread_count == 2


async def test_hybrid_message_uses_its_own_channel(provisioned_tenant):
    """A webchat message injected into a WhatsApp conversation keeps its channel."""
    from one.comms.models import Message
    from one.comms.service import InboundMessage, ingest_inbound, post_outbound
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        wa = await _make_channel(session, "whatsapp")
        web = await _make_channel(session, "webchat")
        conv, _m, _c = await ingest_inbound(
            session, InboundMessage(channel_id=str(wa.id), address="5551777", body="oi", provider_message_id="p1")
        )
        injected = await post_outbound(
            session, conversation_id=str(conv.id), body="chat ao vivo", channel_id=str(web.id)
        )
        reloaded = await session.get(Message, injected.id)

    # conversation anchored to whatsapp, but this message flowed via webchat
    assert str(conv.primary_channel_id) == str(wa.id)
    assert str(reloaded.channel_id) == str(web.id)


async def test_note_is_internal_and_keeps_unread(provisioned_tenant):
    from one.comms.models import MessageStatus, MessageType
    from one.comms.service import InboundMessage, ingest_inbound, post_outbound
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        ch = await _make_channel(session)
        conv, _m, _c = await ingest_inbound(
            session, InboundMessage(channel_id=str(ch.id), address="5551666", body="oi", provider_message_id="n1")
        )
        note = await post_outbound(
            session, conversation_id=str(conv.id), body="lembrete interno", type=MessageType.note
        )

    assert note.type == MessageType.note and note.status == MessageStatus.sent


async def test_lead_from_conversation(provisioned_tenant):
    from decimal import Decimal

    from one.comms.service import InboundMessage, ingest_inbound
    from one.crm.service import create_lead
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        ch = await _make_channel(session)
        conv, _m, _c = await ingest_inbound(
            session, InboundMessage(channel_id=str(ch.id), address="5551555", display_name="Dona Zélia", body="quero", provider_message_id="l1")
        )
        lead = await create_lead(
            session,
            name="Dona Zélia — padaria",
            partner_id=str(conv.partner_id),
            value=Decimal("3200.00"),
            conversation_id=str(conv.id),
        )

    assert lead.partner_id == conv.partner_id
    assert str(lead.conversation_id) == str(conv.id)


def test_whatsapp_adapter_parses_cloud_payload():
    from one.comms.adapters import parse
    from one.comms.models import ChannelType

    cid = str(uuid.uuid4())
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "5551999", "profile": {"name": "Alex"}}],
                            "messages": [
                                {"from": "5551999", "id": "wamid.X", "type": "text", "text": {"body": "Olá"}}
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msgs = parse(ChannelType.whatsapp, cid, payload)
    assert len(msgs) == 1
    assert msgs[0].address == "5551999" and msgs[0].body == "Olá"
    assert msgs[0].display_name == "Alex" and msgs[0].provider_message_id == "wamid.X"
