"""Per-request tenant context, carried in a ContextVar so any layer can read it."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    slug: str
    tenant_id: str


_current: ContextVar[TenantContext | None] = ContextVar("current_tenant", default=None)


def set_current_tenant(ctx: TenantContext) -> None:
    _current.set(ctx)


def get_current_tenant() -> TenantContext | None:
    return _current.get()


def require_current_tenant() -> TenantContext:
    ctx = _current.get()
    if ctx is None:
        raise LookupError("No tenant in context")
    return ctx
