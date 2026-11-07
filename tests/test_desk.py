"""Help Desk + 24h window — ticket creation/SLA and the WhatsApp window helper."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ONE_TEST_DATABASE_URL"), reason="ONE_TEST_DATABASE_URL not set"
)


def test_window_helper():
    from one.comms.service import WINDOW_MS, within_24h_window

    now = 1_000_000_000_000
    assert within_24h_window(now - 1000, at=now) is True
    assert within_24h_window(now - WINDOW_MS - 1, at=now) is False
    assert within_24h_window(None, at=now) is False


async def test_create_ticket_sets_number_and_sla(provisioned_tenant):
    from one.db.session import tenant_session
    from one.desk.models import SlaState, TicketPriority, TicketStatus
    from one.desk.service import create_ticket, set_status

    async with tenant_session(provisioned_tenant) as session:
        t = await create_ticket(
            session, subject="Dúvida sobre convênio", priority=TicketPriority.high
        )
        assert t.number is not None
        assert t.status == TicketStatus.open
        assert t.sla_state == SlaState.running and t.sla_due_at is not None

        t2 = await set_status(session, ticket_id=str(t.id), status=TicketStatus.resolved)
        assert t2.sla_state == SlaState.met


async def test_ingest_sets_inbound_window(provisioned_tenant):
    from one.comms.models import Channel, ChannelType
    from one.comms.service import InboundMessage, ingest_inbound, within_24h_window
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        ch = Channel(type=ChannelType.whatsapp, name="wa", external_id="x")
        session.add(ch)
        await session.flush()
        conv, _m, _c = await ingest_inbound(
            session,
            InboundMessage(channel_id=str(ch.id), address="5551000", body="oi", provider_message_id="w1"),
        )
        assert conv.last_inbound_at is not None
        assert within_24h_window(conv.last_inbound_at) is True
