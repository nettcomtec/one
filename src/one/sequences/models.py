"""Gapless, concurrency-safe numbering (invoices, moves, fiscal docs...).

One row per sequence code per tenant. ``next_number`` locks the row
(SELECT ... FOR UPDATE) so concurrent requests never collide — essential for
fiscal document numbering where gaps and duplicates are both unacceptable.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from one.db.base import TenantBase
from one.db.mixins import PKMixin, TimestampMixin


class Sequence(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "seq_sequence"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    padding: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    next_value: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
