"""Inventory REST — products, stock levels, warehouses and moves.

The products endpoint powers the table (on-hand + status per product); the
moves endpoint is the single write path for stock (entrada / saída / ajuste /
transferência), enforcing availability.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from one.api.deps import current_principal, db_session
from one.identity.security import Principal
from one.inventory.models import (
    Category,
    MoveKind,
    Product,
    ProductKind,
    StockMove,
    StockQuant,
    Warehouse,
)
from one.inventory.service import (
    InsufficientStock,
    create_product,
    ensure_default_warehouse,
    on_hand,
    product_rows,
    record_move,
    stats,
    stock_status,
)

router = APIRouter(prefix="/inv", tags=["inventory"])


def _dec(raw: str | None, default: str = "0") -> Decimal:
    s = str(raw if raw not in (None, "") else default).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Número inválido") from exc


@router.get("/stats")
async def get_stats(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await stats(session)


# --------------------------------------------------------------------------- products
@router.get("/products")
async def list_products(
    q: str | None = None,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    return await product_rows(session, q=q)


class ProductIn(BaseModel):
    name: str
    sku: str | None = None
    unit: str = "UN"
    kind: str = "product"
    price: str = "0"
    cost: str = "0"
    category_id: str | None = None
    barcode: str | None = None
    ncm: str | None = None
    min_stock: str = "0"


@router.post("/products")
async def add_product(
    body: ProductIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        kind = ProductKind(body.kind)
    except ValueError:
        kind = ProductKind.product
    p = await create_product(
        session,
        name=body.name,
        sku=body.sku or None,
        unit=body.unit or "UN",
        kind=kind,
        price=_dec(body.price),
        cost=_dec(body.cost),
        category_id=body.category_id,
        barcode=body.barcode or None,
        ncm=body.ncm or None,
        min_stock=_dec(body.min_stock),
        created_by=principal.user_id,
    )
    await session.commit()
    return {"id": str(p.id), "name": p.name}


@router.get("/products/{product_id}")
async def product_detail(
    product_id: str,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    p = await session.get(Product, uuid.UUID(product_id))
    if p is None or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    qty = await on_hand(session, p.id)
    # per-warehouse balances
    wh_names = {
        w.id: w.name for w in (await session.scalars(select(Warehouse))).all()
    }
    quants = (
        await session.scalars(select(StockQuant).where(StockQuant.product_id == p.id))
    ).all()
    moves = (
        await session.scalars(
            select(StockMove)
            .where(StockMove.product_id == p.id)
            .order_by(desc(StockMove.created_at))
            .limit(20)
        )
    ).all()
    cat = await session.get(Category, p.category_id) if p.category_id else None
    return {
        "id": str(p.id),
        "sku": p.sku,
        "name": p.name,
        "kind": p.kind.value,
        "unit": p.unit,
        "price": f"{p.price:.2f}",
        "cost": f"{p.cost:.2f}",
        "barcode": p.barcode,
        "ncm": p.ncm,
        "min_stock": f"{p.min_stock:.3f}".rstrip("0").rstrip(".") or "0",
        "category": cat.name if cat else None,
        "track_stock": p.track_stock,
        "on_hand": f"{qty:.3f}".rstrip("0").rstrip(".") or "0",
        "status": stock_status(p, qty),
        "warehouses": [
            {
                "warehouse": wh_names.get(qt.warehouse_id, "—"),
                "quantity": f"{qt.quantity:.3f}".rstrip("0").rstrip(".") or "0",
            }
            for qt in quants
        ],
        "moves": [
            {
                "id": str(m.id),
                "kind": m.kind.value,
                "quantity": f"{m.quantity:.3f}".rstrip("0").rstrip(".") or "0",
                "balance_after": f"{m.balance_after:.3f}".rstrip("0").rstrip(".") or "0",
                "reason": m.reason,
                "reference": m.reference,
                "at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in moves
        ],
    }


class ProductPatch(BaseModel):
    name: str | None = None
    sku: str | None = None
    unit: str | None = None
    price: str | None = None
    cost: str | None = None
    barcode: str | None = None
    ncm: str | None = None
    min_stock: str | None = None
    active: bool | None = None


@router.patch("/products/{product_id}")
async def patch_product(
    product_id: str,
    body: ProductPatch,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    p = await session.get(Product, uuid.UUID(product_id))
    if p is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    if body.name is not None:
        p.name = body.name
    if body.sku is not None:
        p.sku = body.sku or None
    if body.unit is not None:
        p.unit = body.unit
    if body.price is not None:
        p.price = _dec(body.price)
    if body.cost is not None:
        p.cost = _dec(body.cost)
    if body.barcode is not None:
        p.barcode = body.barcode or None
    if body.ncm is not None:
        p.ncm = body.ncm or None
    if body.min_stock is not None:
        p.min_stock = _dec(body.min_stock)
    if body.active is not None:
        p.active = body.active
    await session.flush()
    await session.commit()
    return {"id": str(p.id)}


# --------------------------------------------------------------------------- warehouses
@router.get("/warehouses")
async def list_warehouses(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    # Read before commit: SET LOCAL search_path is scoped to the transaction, so
    # committing here would drop the tenant schema for any query that follows.
    await ensure_default_warehouse(session)
    rows = (await session.scalars(select(Warehouse).order_by(Warehouse.name))).all()
    await session.commit()
    return [
        {"id": str(w.id), "code": w.code, "name": w.name, "is_default": w.is_default} for w in rows
    ]


# --------------------------------------------------------------------------- moves
@router.get("/moves")
async def list_moves(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
    limit: int = 50,
) -> list[dict]:
    rows = (
        await session.scalars(
            select(StockMove).order_by(desc(StockMove.created_at)).limit(min(limit, 200))
        )
    ).all()
    pids = {m.product_id for m in rows}
    names: dict[uuid.UUID, str] = {}
    if pids:
        for p in (await session.scalars(select(Product).where(Product.id.in_(pids)))).all():
            names[p.id] = p.name
    return [
        {
            "id": str(m.id),
            "product": names.get(m.product_id, "—"),
            "kind": m.kind.value,
            "quantity": f"{m.quantity:.3f}".rstrip("0").rstrip(".") or "0",
            "balance_after": f"{m.balance_after:.3f}".rstrip("0").rstrip(".") or "0",
            "reason": m.reason,
            "at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


class MoveIn(BaseModel):
    product_id: str
    kind: str  # in | out | adjust | transfer
    quantity: str
    warehouse_id: str | None = None
    dest_warehouse_id: str | None = None
    unit_cost: str = "0"
    reason: str | None = None
    reference: str | None = None


@router.post("/moves")
async def create_move(
    body: MoveIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    try:
        kind = MoveKind(body.kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Tipo de movimento inválido") from exc
    try:
        move = await record_move(
            session,
            product_id=body.product_id,
            kind=kind,
            quantity=_dec(body.quantity),
            warehouse_id=body.warehouse_id,
            dest_warehouse_id=body.dest_warehouse_id,
            unit_cost=_dec(body.unit_cost),
            reason=body.reason,
            reference=body.reference,
            created_by=principal.user_id,
        )
    except InsufficientStock as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    return {
        "id": str(move.id),
        "balance_after": f"{move.balance_after:.3f}".rstrip("0").rstrip(".") or "0",
    }
