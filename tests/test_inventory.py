"""Inventory: moves keep balances honest, block negatives, value stock, alert low.

Needs Postgres (CI provides it).
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

_DB = os.environ.get("ONE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _DB, reason="needs ONE_TEST_DATABASE_URL")


async def test_inbound_outbound_keeps_balance(provisioned_tenant):
    from one.db.session import tenant_session
    from one.inventory.models import MoveKind
    from one.inventory.service import create_product, on_hand, record_move

    async with tenant_session(provisioned_tenant) as s:
        p = await create_product(s, name="Cabo HDMI 2m", sku="CAB-HDMI", cost=Decimal("12.00"))
        m1 = await record_move(
            s, product_id=str(p.id), kind=MoveKind.inbound, quantity=Decimal("50"),
            unit_cost=Decimal("12.00"), reason="Compra NF 123",
        )
        assert m1.balance_after == Decimal("50.000")
        m2 = await record_move(
            s, product_id=str(p.id), kind=MoveKind.outbound, quantity=Decimal("8"), reason="Venda",
        )
        assert m2.balance_after == Decimal("42.000")
        assert await on_hand(s, p.id) == Decimal("42.000")


async def test_outbound_beyond_stock_is_blocked(provisioned_tenant):
    from one.db.session import tenant_session
    from one.inventory.models import MoveKind
    from one.inventory.service import InsufficientStock, create_product, record_move

    async with tenant_session(provisioned_tenant) as s:
        p = await create_product(s, name="Mouse", sku="MOU-1")
        await record_move(s, product_id=str(p.id), kind=MoveKind.inbound, quantity=Decimal("3"))
        with pytest.raises(InsufficientStock):
            await record_move(
                s, product_id=str(p.id), kind=MoveKind.outbound, quantity=Decimal("5")
            )


async def test_adjust_sets_counted_quantity(provisioned_tenant):
    from one.db.session import tenant_session
    from one.inventory.models import MoveKind
    from one.inventory.service import create_product, on_hand, record_move

    async with tenant_session(provisioned_tenant) as s:
        p = await create_product(s, name="Teclado", sku="TEC-1")
        await record_move(s, product_id=str(p.id), kind=MoveKind.inbound, quantity=Decimal("10"))
        # physical count found 7
        m = await record_move(
            s, product_id=str(p.id), kind=MoveKind.adjust, quantity=Decimal("7")
        )
        assert m.balance_after == Decimal("7.000")
        assert m.quantity == Decimal("3.000")  # delta magnitude
        assert await on_hand(s, p.id) == Decimal("7.000")


async def test_transfer_between_warehouses(provisioned_tenant):
    from sqlalchemy import select

    from one.db.session import tenant_session
    from one.inventory.models import MoveKind, StockQuant, Warehouse
    from one.inventory.service import (
        create_product,
        ensure_default_warehouse,
        on_hand,
        record_move,
    )

    async with tenant_session(provisioned_tenant) as s:
        src = await ensure_default_warehouse(s)
        dest = Warehouse(code="LOJA", name="Loja Centro")
        s.add(dest)
        await s.flush()
        p = await create_product(s, name="Fonte 12V", sku="FON-12")
        await record_move(
            s, product_id=str(p.id), kind=MoveKind.inbound, quantity=Decimal("20"),
            warehouse_id=str(src.id),
        )
        await record_move(
            s, product_id=str(p.id), kind=MoveKind.transfer, quantity=Decimal("5"),
            warehouse_id=str(src.id), dest_warehouse_id=str(dest.id),
        )
        # total unchanged, split across warehouses
        assert await on_hand(s, p.id) == Decimal("20.000")
        dest_q = await s.scalar(
            select(StockQuant).where(
                StockQuant.product_id == p.id, StockQuant.warehouse_id == dest.id
            )
        )
        assert dest_q.quantity == Decimal("5.000")


async def test_stats_value_and_low_out(provisioned_tenant):
    from one.db.session import tenant_session
    from one.inventory.models import MoveKind
    from one.inventory.service import create_product, record_move, stats

    async with tenant_session(provisioned_tenant) as s:
        a = await create_product(
            s, name="Produto A", cost=Decimal("10.00"), min_stock=Decimal("5")
        )
        b = await create_product(
            s, name="Produto B", cost=Decimal("4.00"), min_stock=Decimal("5")
        )
        await create_product(s, name="Produto C zerado", min_stock=Decimal("2"))
        await record_move(s, product_id=str(a.id), kind=MoveKind.inbound, quantity=Decimal("10"))
        await record_move(s, product_id=str(b.id), kind=MoveKind.inbound, quantity=Decimal("3"))
        st = await stats(s)
        assert st["sku_count"] == 3
        # value = 10*10 + 3*4 = 112
        assert st["stock_value"] == "112.00"
        assert st["low_count"] == 1  # B (3 <= 5)
        assert st["out_count"] == 1  # C (0)
