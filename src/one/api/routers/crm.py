"""CRM REST — pipeline board, deals, activities and contacts.

The board/stats endpoints feed the kanban; the deal + activity endpoints drive
the detail drawer; the contacts endpoints back the contacts list/detail. Every
write keeps ``last_activity_at`` fresh so the rotting signal stays honest.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from one.api.deps import current_principal, db_session
from one.crm.models import (
    Activity,
    ActivityKind,
    Lead,
    LostReason,
    Partner,
    PartnerKind,
    Stage,
)
from one.crm.service import (
    board,
    complete_activity,
    create_activity,
    create_lead,
    ensure_lost_reasons,
    mark_lost,
    mark_won,
    move_lead,
    pipeline_stats,
)
from one.identity.security import Principal

router = APIRouter(prefix="/crm", tags=["crm"])


def _money(raw: str) -> Decimal:
    """Parse a value accepting pt-BR ('2.500,00') or plain ('2500.00') notation."""
    s = str(raw).strip()
    if "," in s:  # pt-BR: strip thousand dots, comma is the decimal sep
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s or "0")
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Valor inválido") from exc


# --------------------------------------------------------------------------- board
@router.get("/board")
async def get_board(
    pipeline_id: str | None = None,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    data = await board(session, pipeline_id=pipeline_id)
    stats = await pipeline_stats(session, pipeline_id=data["pipeline"]["id"])
    data["stats"] = stats
    return data


@router.get("/stats")
async def get_stats(
    pipeline_id: str | None = None,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await pipeline_stats(session, pipeline_id=pipeline_id)


# --------------------------------------------------------------------------- deals
class DealIn(BaseModel):
    name: str
    partner_id: str | None = None
    value: str = "0"
    source: str | None = None
    stage_id: str | None = None
    expected_close_on: date | None = None


@router.post("/deals")
async def create_deal(
    body: DealIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    lead = await create_lead(
        session,
        name=body.name,
        partner_id=body.partner_id,
        value=_money(body.value),
        source=body.source,
        stage_id=body.stage_id,
        expected_close_on=body.expected_close_on,
        owner_user_id=principal.user_id,
    )
    await session.commit()
    return {"id": str(lead.id), "name": lead.name}


@router.get("/deals/{deal_id}")
async def deal_detail(
    deal_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    lead = await session.get(Lead, uuid.UUID(deal_id))
    if lead is None:
        raise HTTPException(status_code=404, detail="Negócio não encontrado")
    stage = await session.get(Stage, lead.stage_id)
    partner = await session.get(Partner, lead.partner_id) if lead.partner_id else None
    acts = (
        await session.scalars(
            select(Activity)
            .where(Activity.lead_id == lead.id)
            .order_by(
                Activity.done,
                Activity.due_at.is_(None),
                Activity.due_at,
                Activity.created_at.desc(),
            )
        )
    ).all()
    return {
        "id": str(lead.id),
        "name": lead.name,
        "value": f"{lead.value:.2f}",
        "probability": lead.probability,
        "status": lead.status.value,
        "source": lead.source,
        "lost_reason": lead.lost_reason,
        "expected_close_on": lead.expected_close_on.isoformat() if lead.expected_close_on else None,
        "stage": {"id": str(stage.id), "name": stage.name} if stage else None,
        "partner": (
            {
                "id": str(partner.id),
                "name": partner.name,
                "email": partner.email,
                "phone": partner.phone,
            }
            if partner
            else None
        ),
        "conversation_id": str(lead.conversation_id) if lead.conversation_id else None,
        "activities": [
            {
                "id": str(a.id),
                "kind": a.kind.value,
                "subject": a.subject,
                "notes": a.notes,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "done": a.done,
                "done_at": a.done_at.isoformat() if a.done_at else None,
            }
            for a in acts
        ],
    }


class DealPatch(BaseModel):
    name: str | None = None
    value: str | None = None
    probability: int | None = None
    expected_close_on: date | None = None
    source: str | None = None
    partner_id: str | None = None


@router.patch("/deals/{deal_id}")
async def patch_deal(
    deal_id: str,
    body: DealPatch,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    lead = await session.get(Lead, uuid.UUID(deal_id))
    if lead is None:
        raise HTTPException(status_code=404, detail="Negócio não encontrado")
    if body.name is not None:
        lead.name = body.name
    if body.value is not None:
        lead.value = _money(body.value)
    if body.probability is not None:
        lead.probability = max(0, min(100, body.probability))
    if body.expected_close_on is not None:
        lead.expected_close_on = body.expected_close_on
    if body.source is not None:
        lead.source = body.source
    if body.partner_id is not None:
        lead.partner_id = uuid.UUID(body.partner_id) if body.partner_id else None
    await session.flush()
    await session.commit()
    return {"id": str(lead.id)}


class MoveIn(BaseModel):
    stage_id: str
    board_order: int | None = None


@router.post("/deals/{deal_id}/move")
async def move_deal(
    deal_id: str,
    body: MoveIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        lead = await move_lead(
            session, lead_id=deal_id, stage_id=body.stage_id, board_order=body.board_order
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"id": str(lead.id), "status": lead.status.value, "stage_id": str(lead.stage_id)}


@router.post("/deals/{deal_id}/won")
async def win_deal(
    deal_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        lead = await mark_won(session, lead_id=deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"id": str(lead.id), "status": lead.status.value}


class LostIn(BaseModel):
    reason: str | None = None


@router.post("/deals/{deal_id}/lost")
async def lose_deal(
    deal_id: str,
    body: LostIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        lead = await mark_lost(session, lead_id=deal_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"id": str(lead.id), "status": lead.status.value}


# --------------------------------------------------------------------------- activities
class ActivityIn(BaseModel):
    subject: str
    kind: str = "task"
    due_at: datetime | None = None
    notes: str | None = None
    partner_id: str | None = None


@router.post("/deals/{deal_id}/activities")
async def add_activity(
    deal_id: str,
    body: ActivityIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        kind = ActivityKind(body.kind)
    except ValueError:
        kind = ActivityKind.task
    act = await create_activity(
        session,
        subject=body.subject,
        kind=kind,
        lead_id=deal_id,
        partner_id=body.partner_id,
        due_at=body.due_at,
        notes=body.notes,
        owner_user_id=principal.user_id,
    )
    await session.commit()
    return {"id": str(act.id)}


@router.post("/activities/{activity_id}/complete")
async def finish_activity(
    activity_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        act = await complete_activity(session, activity_id=activity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"id": str(act.id), "done": act.done}


@router.get("/agenda")
async def agenda(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
    limit: int = 50,
) -> list[dict]:
    """Open activities with a due date, soonest first — the rep's to-do list."""
    acts = (
        await session.scalars(
            select(Activity)
            .where(Activity.done.is_(False), Activity.due_at.isnot(None))
            .order_by(Activity.due_at)
            .limit(min(limit, 200))
        )
    ).all()
    lead_ids = {a.lead_id for a in acts if a.lead_id}
    deal_names: dict[uuid.UUID, str] = {}
    if lead_ids:
        for ld in (await session.scalars(select(Lead).where(Lead.id.in_(lead_ids)))).all():
            deal_names[ld.id] = ld.name
    return [
        {
            "id": str(a.id),
            "kind": a.kind.value,
            "subject": a.subject,
            "due_at": a.due_at.isoformat() if a.due_at else None,
            "deal_id": str(a.lead_id) if a.lead_id else None,
            "deal_name": deal_names.get(a.lead_id) if a.lead_id else None,
        }
        for a in acts
    ]


# --------------------------------------------------------------------------- contacts
class ContactIn(BaseModel):
    name: str
    kind: str = "person"
    email: str | None = None
    phone: str | None = None
    doc: str | None = None
    company_id: str | None = None
    job_title: str | None = None
    city: str | None = None
    state: str | None = None


@router.get("/contacts")
async def list_contacts(
    q: str | None = None,
    kind: str | None = None,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
    limit: int = 100,
) -> list[dict]:
    stmt = (
        select(Partner)
        .where(Partner.deleted_at.is_(None))
        .order_by(Partner.name)
        .limit(min(limit, 300))
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Partner.name.ilike(like), Partner.email.ilike(like), Partner.doc.ilike(like))
        )
    if kind in ("person", "company"):
        stmt = stmt.where(Partner.kind == PartnerKind(kind))
    rows = (await session.scalars(stmt)).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "kind": p.kind.value,
            "email": p.email,
            "phone": p.phone,
            "doc": p.doc,
            "job_title": p.job_title,
            "city": p.city,
            "state": p.state,
        }
        for p in rows
    ]


@router.post("/contacts")
async def create_contact(
    body: ContactIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        kind = PartnerKind(body.kind)
    except ValueError:
        kind = PartnerKind.person
    p = Partner(
        name=body.name,
        kind=kind,
        email=body.email,
        phone=body.phone,
        doc=body.doc,
        company_id=uuid.UUID(body.company_id) if body.company_id else None,
        job_title=body.job_title,
        city=body.city,
        state=body.state,
        owner_user_id=uuid.UUID(principal.user_id) if principal.user_id else None,
    )
    session.add(p)
    await session.flush()
    await session.commit()
    return {"id": str(p.id), "name": p.name}


@router.get("/contacts/{contact_id}")
async def contact_detail(
    contact_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    p = await session.get(Partner, uuid.UUID(contact_id))
    if p is None or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    deals = (
        await session.scalars(
            select(Lead).where(Lead.partner_id == p.id).order_by(Lead.created_at.desc())
        )
    ).all()
    acts = (
        await session.scalars(
            select(Activity)
            .where(Activity.partner_id == p.id)
            .order_by(Activity.done, Activity.due_at)
            .limit(50)
        )
    ).all()
    company = await session.get(Partner, p.company_id) if p.company_id else None
    return {
        "id": str(p.id),
        "name": p.name,
        "kind": p.kind.value,
        "email": p.email,
        "phone": p.phone,
        "doc": p.doc,
        "job_title": p.job_title,
        "city": p.city,
        "state": p.state,
        "notes": p.notes,
        "company": {"id": str(company.id), "name": company.name} if company else None,
        "deals": [
            {
                "id": str(d.id),
                "name": d.name,
                "value": f"{d.value:.2f}",
                "status": d.status.value,
            }
            for d in deals
        ],
        "activities": [
            {
                "id": str(a.id),
                "kind": a.kind.value,
                "subject": a.subject,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "done": a.done,
            }
            for a in acts
        ],
    }


class ContactPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    doc: str | None = None
    job_title: str | None = None
    city: str | None = None
    state: str | None = None
    notes: str | None = None


@router.patch("/contacts/{contact_id}")
async def patch_contact(
    contact_id: str,
    body: ContactPatch,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    p = await session.get(Partner, uuid.UUID(contact_id))
    if p is None:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    for field in ("name", "email", "phone", "doc", "job_title", "city", "state", "notes"):
        val = getattr(body, field)
        if val is not None:
            setattr(p, field, val)
    await session.flush()
    await session.commit()
    return {"id": str(p.id)}


@router.get("/lost-reasons")
async def lost_reasons(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    # Read before commit: SET LOCAL search_path is transaction-scoped, so a commit
    # here would drop the tenant schema for the SELECT that follows.
    await ensure_lost_reasons(session)
    rows = (
        await session.scalars(
            select(LostReason).where(LostReason.active.is_(True)).order_by(LostReason.sequence)
        )
    ).all()
    await session.commit()
    return [{"id": str(r.id), "name": r.name} for r in rows]
