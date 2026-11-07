"""Ledger service — the only sanctioned way to create accounting entries.

``validate_balance`` is a pure function (no DB) so the core invariant is unit
tested in isolation. ``post_move`` wraps it, assigns the sequence number, and
flips the Move to ``posted``.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from one.ledger.models import Move, MoveLine, MoveState
from one.sequences.service import next_number

CENT = Decimal("0.01")


class UnbalancedMoveError(ValueError):
    pass


class EmptyMoveError(ValueError):
    pass


@dataclass(frozen=True)
class LineInput:
    account_id: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    label: str | None = None


def validate_balance(lines: Sequence[LineInput]) -> None:
    """Raise unless the lines form a non-empty, balanced entry."""
    if not lines:
        raise EmptyMoveError("A move needs at least two lines")
    total_debit = sum((ln.debit for ln in lines), Decimal("0.00")).quantize(CENT)
    total_credit = sum((ln.credit for ln in lines), Decimal("0.00")).quantize(CENT)
    if total_debit != total_credit:
        raise UnbalancedMoveError(
            f"Debit {total_debit} != credit {total_credit}"
        )
    if total_debit == Decimal("0.00"):
        raise UnbalancedMoveError("A move cannot be entirely zero")


async def post_move(
    session: AsyncSession,
    *,
    journal_id: str,
    lines: Sequence[LineInput],
    ref: str | None = None,
    actor: str | None = None,
) -> Move:
    validate_balance(lines)
    move = Move(journal_id=journal_id, ref=ref, state=MoveState.draft, created_by=actor)
    move.lines = [
        MoveLine(
            account_id=ln.account_id,
            debit=ln.debit.quantize(CENT),
            credit=ln.credit.quantize(CENT),
            label=ln.label,
        )
        for ln in lines
    ]
    session.add(move)
    await session.flush()
    move.name = await next_number(session, code="account.move")
    move.state = MoveState.posted
    await session.flush()
    return move
