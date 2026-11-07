"""Identity & RBAC — our own, no GoTrue.

Users live inside each tenant's schema (so a person is scoped to the tenant
they belong to). Permissions are string codes shaped ``<module>.<action>``,
e.g. ``ledger.post``, ``crm.lead.read``. Roles bundle permissions; users hold
roles. Fine-grained per-record rules hang off this later via record rules, but
the permission check below already gives module/action granularity.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Table, Column
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from one.db.base import TenantBase
from one.db.mixins import PKMixin, TimestampMixin

role_permission = Table(
    "idn_role_permission",
    TenantBase.metadata,
    Column("role_id", PgUUID(as_uuid=True), ForeignKey("idn_role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", PgUUID(as_uuid=True), ForeignKey("idn_permission.id", ondelete="CASCADE"), primary_key=True),
)

user_role = Table(
    "idn_user_role",
    TenantBase.metadata,
    Column("user_id", PgUUID(as_uuid=True), ForeignKey("idn_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PgUUID(as_uuid=True), ForeignKey("idn_role.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "idn_permission"
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Role(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "idn_role"
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permission, lazy="selectin"
    )


class User(TenantBase, PKMixin, TimestampMixin):
    __tablename__ = "idn_user"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    roles: Mapped[list[Role]] = relationship(secondary=user_role, lazy="selectin")

    def permission_codes(self) -> set[str]:
        if self.is_admin:
            return {"*"}
        return {p.code for role in self.roles for p in role.permissions}

    def has_permission(self, code: str) -> bool:
        codes = self.permission_codes()
        return "*" in codes or code in codes
