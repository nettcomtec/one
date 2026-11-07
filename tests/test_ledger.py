"""The accounting invariant, tested without a database."""

from decimal import Decimal

import pytest

from one.ledger.service import (
    EmptyMoveError,
    LineInput,
    UnbalancedMoveError,
    validate_balance,
)


def test_balanced_move_passes():
    lines = [
        LineInput(account_id="a", debit=Decimal("100.00")),
        LineInput(account_id="b", credit=Decimal("100.00")),
    ]
    validate_balance(lines)  # no raise


def test_unbalanced_move_raises():
    lines = [
        LineInput(account_id="a", debit=Decimal("100.00")),
        LineInput(account_id="b", credit=Decimal("90.00")),
    ]
    with pytest.raises(UnbalancedMoveError):
        validate_balance(lines)


def test_empty_move_raises():
    with pytest.raises(EmptyMoveError):
        validate_balance([])


def test_all_zero_move_raises():
    lines = [
        LineInput(account_id="a", debit=Decimal("0.00")),
        LineInput(account_id="b", credit=Decimal("0.00")),
    ]
    with pytest.raises(UnbalancedMoveError):
        validate_balance(lines)


def test_cent_rounding_balances():
    lines = [
        LineInput(account_id="a", debit=Decimal("33.33")),
        LineInput(account_id="b", debit=Decimal("33.33")),
        LineInput(account_id="c", debit=Decimal("33.34")),
        LineInput(account_id="d", credit=Decimal("100.00")),
    ]
    validate_balance(lines)
