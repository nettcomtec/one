"""CRM services — pipeline bootstrap and lead creation (incl. from a conversation)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from one.crm.models import Lead, Pipeline, Stage

_DEFAULT_STAGES = [
    ("Novo", 10, False, False),
    ("Qualificado", 20, False, False),
    ("Proposta", 30, False, False),
    ("Ganho", 40, True, False),
    ("Perdido", 50, False, True),
]


async def ensure_default_pipeline(session: AsyncSession) -> Pipeline:
    pipe = await session.scalar(select(Pipeline).where(Pipeline.is_default.is_(True)))
    if pipe is not None:
        return pipe
    pipe = Pipeline(name="Vendas", is_default=True)
    session.add(pipe)
    await session.flush()
    for name, seq, won, lost in _DEFAULT_STAGES:
        session.add(Stage(pipeline_id=pipe.id, name=name, sequence=seq, is_won=won, is_lost=lost))
    await session.flush()
    return pipe


async def _first_stage(session: AsyncSession, pipeline_id) -> Stage:
    return await session.scalar(
        select(Stage).where(Stage.pipeline_id == pipeline_id).order_by(Stage.sequence)
    )


async def create_lead(
    session: AsyncSession,
    *,
    name: str,
    partner_id: str | None = None,
    value: Decimal = Decimal("0.00"),
    source: str | None = None,
    conversation_id: str | None = None,
    owner_user_id: str | None = None,
) -> Lead:
    pipe = await ensure_default_pipeline(session)
    stage = await _first_stage(session, pipe.id)
    lead = Lead(
        name=name,
        partner_id=uuid.UUID(partner_id) if partner_id else None,
        pipeline_id=pipe.id,
        stage_id=stage.id,
        value=value,
        source=source,
        conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
        owner_user_id=uuid.UUID(owner_user_id) if owner_user_id else None,
    )
    session.add(lead)
    await session.flush()
    return lead
