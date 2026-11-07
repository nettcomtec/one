"""Double-entry ledger — the accounting backbone every module posts to.

Model (deliberately minimal, Odoo-shaped so it's familiar):

* Account  — a node in the chart of accounts (asset/liability/equity/income/expense).
* Journal  — a book of entries (sales, purchases, bank, misc).
* Move     — a balanced accounting entry (one transaction).
* MoveLine — a debit or credit against one account within a Move.

Invariant: for every posted Move, sum(debit) == sum(credit). Enforced in
ledger.service.post_move and re-checked by a DB constraint-friendly design.
"""
from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from one.db.base import TenantBase
from one.db.mixins import AuditMixin, PKMixin, SoftDeleteMixin, TimestampMixin


class AccountType(str, enum.Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"


class MoveState(str, enum.Enum):
    draft = "draft"
    posted = "posted"
    cancelled = "cancelled"


class Account(TenantBase, PKMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "acc_account"

    code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[AccountType] = mapped_column(Enum(AccountType, name="account_type"), nullable=False)

    __table_args__ = (CheckConstraint("code <> ''", name="code_not_empty"),)


class Journal(TenantBase, PKMixin, TimestampMixin, AuditMixin):
    __tablename__ = "acc_journal"

    code: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Move(TenantBase, PKMixin, TimestampMixin, AuditMixin):
    __tablename__ = "acc_move"

    name: Mapped[str | None] = mapped_column(String(64), nullable=True)  # filled by sequence on post
    ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[MoveState] = mapped_column(
        Enum(MoveState, name="move_state"), default=MoveState.draft, nullable=False
    )
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("acc_journal.id"), nullable=False
    )

    lines: Mapped[list[MoveLine]] = relationship(
        back_populates="move", cascade="all, delete-orphan", lazy="selectin"
    )


class MoveLine(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "acc_move_line"

    move_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("acc_move.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("acc_account.id"), nullable=False
    )
    debit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)

    move: Mapped[Move] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="amounts_non_negative"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="debit_xor_credit"),
    )
