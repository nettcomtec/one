"""Inventory services — moves that keep stock balances honest, plus summaries.

``record_move`` is the one door through which stock changes. It updates the
per-warehouse :class:`StockQuant`, writes a :class:`StockMove` with the running
balance, and refuses an outbound/transfer that would go negative (unless
explicitly allowed). Everything else — on-hand, valuation, low-stock — reads off
those two tables.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from one.inventory.models import (
    Category,
    MoveKind,
    Product,
    ProductKind,
    StockMove,
    StockQuant,
    Warehouse,
)

ZERO = Decimal("0")


class InsufficientStock(ValueError):
    """Raised when an outbound/transfer would drive a balance negative."""


async def ensure_default_warehouse(session: AsyncSession) -> Warehouse:
    wh = await session.scalar(select(Warehouse).where(Warehouse.is_default.is_(True)))
    if wh is not None:
        return wh
    wh = await session.scalar(select(Warehouse).order_by(Warehouse.created_at).limit(1))
    if wh is not None:
        return wh
    wh = Warehouse(code="PRINC", name="Depósito Principal", is_default=True)
    session.add(wh)
    await session.flush()
    return wh


async def _quant(session: AsyncSession, product_id, warehouse_id, *, create: bool = True):
    q = await session.scalar(
        select(StockQuant).where(
            StockQuant.product_id == product_id, StockQuant.warehouse_id == warehouse_id
        )
    )
    if q is None and create:
        q = StockQuant(product_id=product_id, warehouse_id=warehouse_id, quantity=ZERO)
        session.add(q)
        await session.flush()
    return q


async def create_product(
    session: AsyncSession,
    *,
    name: str,
    sku: str | None = None,
    unit: str = "UN",
    kind: ProductKind = ProductKind.product,
    price: Decimal = ZERO,
    cost: Decimal = ZERO,
    category_id: str | None = None,
    barcode: str | None = None,
    ncm: str | None = None,
    min_stock: Decimal = ZERO,
    track_stock: bool = True,
    created_by: str | None = None,
) -> Product:
    p = Product(
        name=name,
        sku=sku,
        unit=unit,
        kind=kind,
        price=price,
        cost=cost,
        category_id=uuid.UUID(category_id) if category_id else None,
        barcode=barcode,
        ncm=ncm,
        min_stock=min_stock,
        track_stock=track_stock and kind is ProductKind.product,
        created_by=created_by,
    )
    session.add(p)
    await session.flush()
    return p


async def record_move(
    session: AsyncSession,
    *,
    product_id: str,
    kind: MoveKind,
    quantity: Decimal,
    warehouse_id: str | None = None,
    dest_warehouse_id: str | None = None,
    unit_cost: Decimal = ZERO,
    reason: str | None = None,
    reference: str | None = None,
    allow_negative: bool = False,
    created_by: str | None = None,
) -> StockMove:
    product = await session.get(Product, uuid.UUID(product_id))
    if product is None:
        raise ValueError("Produto não encontrado")
    if quantity < ZERO:
        raise ValueError("Quantidade não pode ser negativa")

    wh = (
        await session.get(Warehouse, uuid.UUID(warehouse_id))
        if warehouse_id
        else await ensure_default_warehouse(session)
    )
    if wh is None:
        raise ValueError("Depósito não encontrado")

    src = await _quant(session, product.id, wh.id)
    move_qty = quantity

    if kind is MoveKind.inbound:
        src.quantity = (src.quantity or ZERO) + quantity
        if unit_cost and unit_cost > ZERO:
            product.cost = unit_cost  # last-cost valuation
    elif kind is MoveKind.outbound:
        if not allow_negative and (src.quantity or ZERO) < quantity:
            raise InsufficientStock(
                f"Saldo insuficiente: {src.quantity or ZERO} {product.unit} disponível"
            )
        src.quantity = (src.quantity or ZERO) - quantity
    elif kind is MoveKind.adjust:
        # quantity is the counted on-hand; store the delta magnitude.
        target = quantity
        move_qty = abs(target - (src.quantity or ZERO))
        src.quantity = target
        reason = reason or "Ajuste de inventário"
    elif kind is MoveKind.transfer:
        if not dest_warehouse_id:
            raise ValueError("Transferência exige depósito de destino")
        dest = await session.get(Warehouse, uuid.UUID(dest_warehouse_id))
        if dest is None:
            raise ValueError("Depósito de destino não encontrado")
        if not allow_negative and (src.quantity or ZERO) < quantity:
            raise InsufficientStock(
                f"Saldo insuficiente para transferir: {src.quantity or ZERO} {product.unit}"
            )
        src.quantity = (src.quantity or ZERO) - quantity
        dq = await _quant(session, product.id, dest.id)
        dq.quantity = (dq.quantity or ZERO) + quantity
    else:  # pragma: no cover
        raise ValueError("Tipo de movimento inválido")

    await session.flush()
    move = StockMove(
        product_id=product.id,
        kind=kind,
        quantity=move_qty,
        warehouse_id=wh.id,
        dest_warehouse_id=uuid.UUID(dest_warehouse_id) if dest_warehouse_id else None,
        unit_cost=unit_cost,
        balance_after=src.quantity,
        reason=reason,
        reference=reference,
        created_by=created_by,
    )
    session.add(move)
    await session.flush()
    return move


async def on_hand(session: AsyncSession, product_id) -> Decimal:
    total = await session.scalar(
        select(func.coalesce(func.sum(StockQuant.quantity), 0)).where(
            StockQuant.product_id == product_id
        )
    )
    return Decimal(total or 0)


def stock_status(product: Product, qty: Decimal) -> str:
    if not product.track_stock or product.kind is not ProductKind.product:
        return "na"
    if qty <= ZERO:
        return "out"
    if product.min_stock and qty <= product.min_stock:
        return "low"
    return "ok"


async def product_rows(
    session: AsyncSession, *, q: str | None = None, limit: int = 200
) -> list[dict]:
    """Products with their total on-hand and status — backs the inventory table."""
    stmt = select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name)
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_

        stmt = stmt.where(
            or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like))
        )
    products = (await session.scalars(stmt.limit(min(limit, 500)))).all()
    # batch on-hand
    pids = [p.id for p in products]
    totals: dict[uuid.UUID, Decimal] = {}
    if pids:
        rows = (
            await session.execute(
                select(StockQuant.product_id, func.sum(StockQuant.quantity))
                .where(StockQuant.product_id.in_(pids))
                .group_by(StockQuant.product_id)
            )
        ).all()
        totals = {pid: Decimal(t or 0) for pid, t in rows}
    cats: dict[uuid.UUID, str] = {}
    cids = {p.category_id for p in products if p.category_id}
    if cids:
        for c in (await session.scalars(select(Category).where(Category.id.in_(cids)))).all():
            cats[c.id] = c.name
    out = []
    for p in products:
        qty = totals.get(p.id, ZERO)
        out.append(
            {
                "id": str(p.id),
                "sku": p.sku,
                "name": p.name,
                "kind": p.kind.value,
                "unit": p.unit,
                "category": cats.get(p.category_id) if p.category_id else None,
                "price": f"{p.price:.2f}",
                "cost": f"{p.cost:.2f}",
                "on_hand": f"{qty:.3f}".rstrip("0").rstrip(".") or "0",
                "min_stock": f"{p.min_stock:.3f}".rstrip("0").rstrip(".") or "0",
                "status": stock_status(p, qty),
                "track_stock": p.track_stock,
            }
        )
    return out


async def stats(session: AsyncSession) -> dict:
    sku_count = await session.scalar(
        select(func.count()).select_from(Product).where(
            Product.deleted_at.is_(None), Product.active.is_(True)
        )
    )
    # valuation = sum(quant.qty * product.cost)
    value = await session.scalar(
        select(func.coalesce(func.sum(StockQuant.quantity * Product.cost), 0)).where(
            StockQuant.product_id == Product.id
        )
    )
    # per-product totals for low/out counts (only tracked products)
    rows = (
        await session.execute(
            select(
                Product.id,
                Product.min_stock,
                Product.track_stock,
                func.coalesce(func.sum(StockQuant.quantity), 0),
            )
            .select_from(Product)
            .outerjoin(StockQuant, StockQuant.product_id == Product.id)
            .where(Product.deleted_at.is_(None), Product.active.is_(True))
            .group_by(Product.id, Product.min_stock, Product.track_stock)
        )
    ).all()
    low = out = 0
    for _pid, min_s, track, qty in rows:
        if not track:
            continue
        qty = Decimal(qty or 0)
        if qty <= ZERO:
            out += 1
        elif min_s and qty <= Decimal(min_s):
            low += 1
    return {
        "sku_count": sku_count or 0,
        "stock_value": f"{Decimal(value or 0):.2f}",
        "low_count": low,
        "out_count": out,
    }
