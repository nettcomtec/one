"""Allocate the next value of a named sequence, atomically."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from one.sequences.models import Sequence


class UnknownSequenceError(KeyError):
    pass


def format_value(prefix: str, padding: int, value: int) -> str:
    return f"{prefix}{value:0{padding}d}"


async def next_number(session: AsyncSession, *, code: str) -> str:
    """Return the formatted next value for ``code``, locking the row.

    Auto-creates the sequence on first use with sane defaults so a module can
    reference a sequence code without a separate seeding step.
    """
    seq = await session.scalar(select(Sequence).where(Sequence.code == code).with_for_update())
    if seq is None:
        seq = Sequence(code=code, prefix="", padding=5, next_value=1)
        session.add(seq)
        await session.flush()
        # re-select with lock to be safe under concurrency
        seq = await session.scalar(select(Sequence).where(Sequence.code == code).with_for_update())
    value = seq.next_value
    seq.next_value = value + 1
    await session.flush()
    return format_value(seq.prefix, seq.padding, value)
