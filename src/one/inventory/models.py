"""Inventory core — products, categories, warehouses, stock levels and moves.

The model mirrors how the best stock systems (Odoo, Bling, Tiny) keep inventory
honest: the on-hand quantity is never edited directly. Every change is a
``StockMove`` (entrada / saída / ajuste / transferência) and the per-warehouse
balance lives in ``StockQuant``, which the service recomputes as moves are
applied. That gives a full audit trail and makes valuation and low-stock alerts
fall out of the data.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from one.db.base import TenantBase
from one.db.mixins import AuditMixin, PKMixin, SoftDeleteMixin, TimestampMixin

# Quantities keep 3 decimals (KG, L, M); money keeps 2.
_QTY = Numeric(16, 3)
_MONEY = Numeric(16, 2)


class ProductKind(enum.StrEnum):
    product = "product"  # stockable good
    service = "service"  # no stock tracking
    kit = "kit"  # composed of other products


class Category(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "inv_category"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_category.id"), nullable=True
    )


class Product(TenantBase, PKMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "inv_product"

    sku: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    kind: Mapped[ProductKind] = mapped_column(
        Enum(ProductKind, name="product_kind", native_enum=False, length=12),
        default=ProductKind.product,
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(String(8), default="UN", nullable=False)  # UN, KG, CX, L...
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_category.id"), index=True, nullable=True
    )
    barcode: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)  # GTIN/EAN
    ncm: Mapped[str | None] = mapped_column(String(8), nullable=True)  # fiscal classification

    price: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0.00"), nullable=False)
    cost: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0.00"), nullable=False)

    track_stock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_stock: Mapped[Decimal] = mapped_column(_QTY, default=Decimal("0"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Warehouse(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "inv_warehouse"
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class StockQuant(TenantBase, PKMixin, TimestampMixin):
    """On-hand balance of one product in one warehouse. Maintained by the service."""

    __tablename__ = "inv_quant"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id", name="uq_quant_prod_wh"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_product.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_warehouse.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(_QTY, default=Decimal("0"), nullable=False)


class MoveKind(enum.StrEnum):
    inbound = "in"  # entrada (compra, produção, devolução)
    outbound = "out"  # saída (venda, consumo, perda)
    adjust = "adjust"  # ajuste de inventário (contagem)
    transfer = "transfer"  # transferência entre depósitos


class StockMove(TenantBase, PKMixin, TimestampMixin, AuditMixin):
    """One inventory event. The append-only ledger behind every quant."""

    __tablename__ = "inv_move"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_product.id"), index=True, nullable=False
    )
    kind: Mapped[MoveKind] = mapped_column(
        Enum(MoveKind, name="move_kind", native_enum=False, length=10), nullable=False
    )
    # Signed is derived from kind; we store the absolute quantity moved.
    quantity: Mapped[Decimal] = mapped_column(_QTY, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_warehouse.id"), nullable=False
    )
    # For transfers, the destination warehouse.
    dest_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("inv_warehouse.id"), nullable=True
    )
    unit_cost: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0.00"), nullable=False)
    # Resulting on-hand (that warehouse) after this move — a running balance.
    balance_after: Mapped[Decimal] = mapped_column(_QTY, default=Decimal("0"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)  # NF, pedido, etc.
