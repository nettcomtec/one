"""CRM services — pipeline bootstrap, deals, activities, and the board snapshot.

The board snapshot is the heart of the UI: for one pipeline it returns the
stages, the open deals grouped under each, and per deal the *next activity* and
whether it's *rotting* (idle past the stage's threshold) — the two signals that
tell a rep what to do next and which deals are slipping.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from one.crm.models import (
    Activity,
    ActivityKind,
    Lead,
    LeadStatus,
    LostReason,
    Partner,
    Pipeline,
    Stage,
)

# (name, sequence, is_won, is_lost, probability, rotting_days)
_DEFAULT_STAGES = [
    ("Novo", 10, False, False, 10, 7),
    ("Qualificado", 20, False, False, 30, 14),
    ("Proposta", 30, False, False, 60, 10),
    ("Negociação", 40, False, False, 80, 7),
    ("Ganho", 50, True, False, 100, 0),
    ("Perdido", 60, False, True, 0, 0),
]

_DEFAULT_LOST_REASONS = [
    "Preço",
    "Escolheu concorrente",
    "Sem orçamento",
    "Sem resposta",
    "Timing / adiado",
    "Não era fit",
]


def _now() -> datetime:
    return datetime.now(UTC)


async def ensure_default_pipeline(session: AsyncSession) -> Pipeline:
    pipe = await session.scalar(select(Pipeline).where(Pipeline.is_default.is_(True)))
    if pipe is not None:
        return pipe
    pipe = Pipeline(name="Vendas", is_default=True)
    session.add(pipe)
    await session.flush()
    for name, seq, won, lost, prob, rot in _DEFAULT_STAGES:
        session.add(
            Stage(
                pipeline_id=pipe.id,
                name=name,
                sequence=seq,
                is_won=won,
                is_lost=lost,
                probability=prob,
                rotting_days=rot,
            )
        )
    await session.flush()
    return pipe


async def ensure_lost_reasons(session: AsyncSession) -> None:
    existing = await session.scalar(select(func.count()).select_from(LostReason))
    if existing:
        return
    for i, name in enumerate(_DEFAULT_LOST_REASONS, start=1):
        session.add(LostReason(name=name, sequence=i * 10))
    await session.flush()


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
    stage_id: str | None = None,
    expected_close_on: date | None = None,
) -> Lead:
    pipe = await ensure_default_pipeline(session)
    if stage_id:
        stage = await session.get(Stage, uuid.UUID(stage_id))
    else:
        stage = await _first_stage(session, pipe.id)
    lead = Lead(
        name=name,
        partner_id=uuid.UUID(partner_id) if partner_id else None,
        pipeline_id=pipe.id,
        stage_id=stage.id,
        value=value,
        probability=stage.probability,
        source=source,
        expected_close_on=expected_close_on,
        last_activity_at=_now(),
        conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
        owner_user_id=uuid.UUID(owner_user_id) if owner_user_id else None,
    )
    session.add(lead)
    await session.flush()
    return lead


async def move_lead(
    session: AsyncSession, *, lead_id: str, stage_id: str, board_order: int | None = None
) -> Lead:
    """Drag a deal to another stage. Entering a won/lost stage closes the deal."""
    lead = await session.get(Lead, uuid.UUID(lead_id))
    if lead is None:
        raise ValueError("Negócio não encontrado")
    stage = await session.get(Stage, uuid.UUID(stage_id))
    if stage is None:
        raise ValueError("Etapa não encontrada")
    lead.stage_id = stage.id
    lead.probability = stage.probability
    lead.last_activity_at = _now()
    if board_order is not None:
        lead.board_order = board_order
    if stage.is_won:
        lead.status = LeadStatus.won
        lead.closed_at = _now()
    elif stage.is_lost:
        lead.status = LeadStatus.lost
        lead.closed_at = _now()
    else:
        lead.status = LeadStatus.open
        lead.closed_at = None
    await session.flush()
    return lead


async def mark_won(session: AsyncSession, *, lead_id: str) -> Lead:
    lead = await session.get(Lead, uuid.UUID(lead_id))
    if lead is None:
        raise ValueError("Negócio não encontrado")
    won = await session.scalar(
        select(Stage).where(Stage.pipeline_id == lead.pipeline_id, Stage.is_won.is_(True))
    )
    if won:
        lead.stage_id = won.id
        lead.probability = 100
    lead.status = LeadStatus.won
    lead.closed_at = _now()
    lead.last_activity_at = _now()
    await session.flush()
    return lead


async def mark_lost(session: AsyncSession, *, lead_id: str, reason: str | None = None) -> Lead:
    lead = await session.get(Lead, uuid.UUID(lead_id))
    if lead is None:
        raise ValueError("Negócio não encontrado")
    lost = await session.scalar(
        select(Stage).where(Stage.pipeline_id == lead.pipeline_id, Stage.is_lost.is_(True))
    )
    if lost:
        lead.stage_id = lost.id
    lead.status = LeadStatus.lost
    lead.probability = 0
    lead.lost_reason = reason
    lead.closed_at = _now()
    lead.last_activity_at = _now()
    await session.flush()
    return lead


async def create_activity(
    session: AsyncSession,
    *,
    subject: str,
    kind: ActivityKind = ActivityKind.task,
    lead_id: str | None = None,
    partner_id: str | None = None,
    due_at: datetime | None = None,
    notes: str | None = None,
    owner_user_id: str | None = None,
) -> Activity:
    act = Activity(
        subject=subject,
        kind=kind,
        notes=notes,
        due_at=due_at,
        lead_id=uuid.UUID(lead_id) if lead_id else None,
        partner_id=uuid.UUID(partner_id) if partner_id else None,
        owner_user_id=uuid.UUID(owner_user_id) if owner_user_id else None,
    )
    session.add(act)
    await session.flush()
    return act


async def complete_activity(session: AsyncSession, *, activity_id: str) -> Activity:
    act = await session.get(Activity, uuid.UUID(activity_id))
    if act is None:
        raise ValueError("Atividade não encontrada")
    act.done = True
    act.done_at = _now()
    if act.lead_id:
        lead = await session.get(Lead, act.lead_id)
        if lead:
            lead.last_activity_at = _now()
    await session.flush()
    return act


def _is_rotting(lead: Lead, stage: Stage, now: datetime) -> bool:
    if lead.status is not LeadStatus.open or not stage.rotting_days:
        return False
    ref = lead.last_activity_at or lead.created_at
    if ref is None:
        return False
    return now - ref > timedelta(days=stage.rotting_days)


async def board(session: AsyncSession, *, pipeline_id: str | None = None) -> dict:
    """Full kanban snapshot for one pipeline: stages + open deals + signals."""
    if pipeline_id:
        pipe = await session.get(Pipeline, uuid.UUID(pipeline_id))
    else:
        pipe = await ensure_default_pipeline(session)
    stages = (
        await session.scalars(
            select(Stage).where(Stage.pipeline_id == pipe.id).order_by(Stage.sequence)
        )
    ).all()
    stage_by_id = {s.id: s for s in stages}

    leads = (
        await session.scalars(
            select(Lead)
            .where(Lead.pipeline_id == pipe.id, Lead.status == LeadStatus.open)
            .order_by(Lead.board_order, Lead.created_at)
        )
    ).all()

    # names + next activities, batched
    partner_ids = {ld.partner_id for ld in leads if ld.partner_id}
    names: dict[uuid.UUID, str] = {}
    if partner_ids:
        for p in (await session.scalars(select(Partner).where(Partner.id.in_(partner_ids)))).all():
            names[p.id] = p.name

    lead_ids = [ld.id for ld in leads]
    next_act: dict[uuid.UUID, Activity] = {}
    if lead_ids:
        acts = (
            await session.scalars(
                select(Activity)
                .where(
                    Activity.lead_id.in_(lead_ids),
                    Activity.done.is_(False),
                    Activity.due_at.isnot(None),
                )
                .order_by(Activity.due_at)
            )
        ).all()
        for a in acts:
            if a.lead_id not in next_act:
                next_act[a.lead_id] = a

    now = _now()
    cols: dict[uuid.UUID, dict] = {
        s.id: {
            "id": str(s.id),
            "name": s.name,
            "probability": s.probability,
            "is_won": s.is_won,
            "is_lost": s.is_lost,
            "deals": [],
            "total": Decimal("0.00"),
        }
        for s in stages
    }
    for ld in leads:
        stage = stage_by_id.get(ld.stage_id)
        if stage is None:
            continue
        na = next_act.get(ld.id)
        col = cols[stage.id]
        col["total"] += ld.value or Decimal("0.00")
        col["deals"].append(
            {
                "id": str(ld.id),
                "name": ld.name,
                "partner_name": names.get(ld.partner_id) if ld.partner_id else None,
                "value": f"{ld.value:.2f}",
                "probability": ld.probability,
                "source": ld.source,
                "expected_close_on": ld.expected_close_on.isoformat()
                if ld.expected_close_on
                else None,
                "rotting": _is_rotting(ld, stage, now),
                "next_activity": (
                    {
                        "id": str(na.id),
                        "kind": na.kind.value,
                        "subject": na.subject,
                        "due_at": na.due_at.isoformat() if na.due_at else None,
                        "overdue": bool(na.due_at and na.due_at < now),
                    }
                    if na
                    else None
                ),
            }
        )

    columns = []
    for s in stages:
        c = cols[s.id]
        c["total"] = f"{c['total']:.2f}"
        columns.append(c)
    return {
        "pipeline": {"id": str(pipe.id), "name": pipe.name},
        "columns": columns,
    }


async def pipeline_stats(session: AsyncSession, *, pipeline_id: str | None = None) -> dict:
    """Headline numbers: open value, weighted forecast, counts, win rate."""
    if pipeline_id:
        pid = uuid.UUID(pipeline_id)
    else:
        pipe = await ensure_default_pipeline(session)
        pid = pipe.id

    open_leads = (
        await session.scalars(
            select(Lead).where(Lead.pipeline_id == pid, Lead.status == LeadStatus.open)
        )
    ).all()
    open_value = sum((ld.value or Decimal("0.00") for ld in open_leads), Decimal("0.00"))
    weighted = sum(
        (
            (ld.value or Decimal("0.00")) * Decimal(ld.probability) / Decimal(100)
            for ld in open_leads
        ),
        Decimal("0.00"),
    )
    won = await session.scalar(
        select(func.count()).select_from(Lead).where(
            Lead.pipeline_id == pid, Lead.status == LeadStatus.won
        )
    )
    lost = await session.scalar(
        select(func.count()).select_from(Lead).where(
            Lead.pipeline_id == pid, Lead.status == LeadStatus.lost
        )
    )
    decided = (won or 0) + (lost or 0)
    win_rate = round((won or 0) / decided * 100) if decided else 0
    return {
        "open_count": len(open_leads),
        "open_value": f"{open_value:.2f}",
        "forecast": f"{weighted:.2f}",
        "won_count": won or 0,
        "lost_count": lost or 0,
        "win_rate": win_rate,
    }
