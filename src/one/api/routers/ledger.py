"""Ledger HTTP surface — thin: it validates input and calls the service.

Deliberately mirrors the AI tool, proving the point that UI and agent share one
logic path (one.ledger.service.post_move)."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from one.api.deps import current_principal, db_session
from one.identity.security import Principal
from one.ledger.service import LineInput, UnbalancedMoveError, post_move

router = APIRouter(prefix="/ledger", tags=["ledger"])


class LineIn(BaseModel):
    account_id: str
    debit: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0)
    label: str | None = None


class MoveIn(BaseModel):
    journal_id: str
    ref: str | None = None
    lines: list[LineIn] = Field(min_length=2)


@router.post("/moves")
async def create_move(
    body: MoveIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        move = await post_move(
            session,
            journal_id=body.journal_id,
            ref=body.ref,
            actor=principal.user_id,
            lines=[
                LineInput(account_id=l.account_id, debit=l.debit, credit=l.credit, label=l.label)
                for l in body.lines
            ],
        )
    except UnbalancedMoveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": str(move.id), "name": move.name, "state": move.state.value}
