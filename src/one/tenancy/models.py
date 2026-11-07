"""The tenant registry — lives in the ``public`` schema."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from one.db.base import PublicBase
from one.db.mixins import PKMixin, TimestampMixin


class Tenant(PublicBase, PKMixin, TimestampMixin):
    __tablename__ = "tenant"

    slug: Mapped[str] = mapped_column(String(63), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # CNPJ of the tenant's main company (optional at provisioning time).
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tenant {self.slug}>"
