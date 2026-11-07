"""CRM module: pipeline board, deals, stage moves, activities, forecast, rotting.

Needs Postgres (CI provides it).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

_DB = os.environ.get("ONE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _DB, reason="needs ONE_TEST_DATABASE_URL")


async def test_board_has_default_stages_and_deal(provisioned_tenant):
    from one.crm.models import ActivityKind
    from one.crm.service import board, create_activity, create_lead, pipeline_stats
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        lead = await create_lead(session, name="Mensalidade Clínica", value=Decimal("1890.00"))
        await create_activity(
            session,
            subject="Ligar para fechar",
            kind=ActivityKind.call,
            lead_id=str(lead.id),
            due_at=datetime.now(UTC) + timedelta(days=1),
        )
        snap = await board(session)
        stages = [c["name"] for c in snap["columns"]]
        assert stages == ["Novo", "Qualificado", "Proposta", "Negociação", "Ganho", "Perdido"]
        novo = snap["columns"][0]
        assert novo["deals"][0]["name"] == "Mensalidade Clínica"
        assert novo["deals"][0]["value"] == "1890.00"
        # next activity is surfaced on the card
        assert novo["deals"][0]["next_activity"]["kind"] == "call"
        assert novo["total"] == "1890.00"

        stats = await pipeline_stats(session, pipeline_id=snap["pipeline"]["id"])
        assert stats["open_count"] == 1
        assert stats["open_value"] == "1890.00"
        # Novo stage probability is 10% -> forecast 189.00
        assert stats["forecast"] == "189.00"


async def test_move_deal_to_won_closes_it(provisioned_tenant):
    from one.crm.models import LeadStatus
    from one.crm.service import board, create_lead, mark_won
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        lead = await create_lead(session, name="Contrato anual", value=Decimal("12000.00"))
        await mark_won(session, lead_id=str(lead.id))
        assert lead.status is LeadStatus.won
        assert lead.probability == 100
        assert lead.closed_at is not None
        # won deals leave the open board
        snap = await board(session)
        all_deals = [d for c in snap["columns"] for d in c["deals"]]
        assert all_deals == []


async def test_lost_deal_records_reason(provisioned_tenant):
    from one.crm.models import LeadStatus
    from one.crm.service import create_lead, mark_lost
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        lead = await create_lead(session, name="Projeto X", value=Decimal("5000.00"))
        await mark_lost(session, lead_id=str(lead.id), reason="Preço")
        assert lead.status is LeadStatus.lost
        assert lead.lost_reason == "Preço"
        assert lead.probability == 0


async def test_rotting_flag_when_idle_past_threshold(provisioned_tenant):
    from one.crm.service import board, create_lead
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        lead = await create_lead(session, name="Esquecido", value=Decimal("100.00"))
        # Novo stage rots after 7 days — force last activity 10 days ago
        lead.last_activity_at = datetime.now(UTC) - timedelta(days=10)
        await session.flush()
        snap = await board(session)
        card = snap["columns"][0]["deals"][0]
        assert card["rotting"] is True


async def test_complete_activity_refreshes_deal(provisioned_tenant):
    from one.crm.models import ActivityKind
    from one.crm.service import complete_activity, create_activity, create_lead
    from one.db.session import tenant_session

    async with tenant_session(provisioned_tenant) as session:
        lead = await create_lead(session, name="Deal", value=Decimal("1.00"))
        lead.last_activity_at = datetime.now(UTC) - timedelta(days=30)
        await session.flush()
        act = await create_activity(
            session, subject="Enviar proposta", kind=ActivityKind.email, lead_id=str(lead.id)
        )
        await complete_activity(session, activity_id=str(act.id))
        assert act.done is True
        assert act.done_at is not None
        # completing an activity counts as fresh activity on the deal
        assert lead.last_activity_at > datetime.now(UTC) - timedelta(minutes=1)
