"""FastAPI dependencies: tenant-scoped DB session, current principal, permission guard."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from one.db.session import tenant_session
from one.identity.security import Principal, decode_token
from one.tenancy.context import TenantContext


def current_tenant(request: Request) -> TenantContext:
    ctx = getattr(request.state, "tenant", None)
    if ctx is None:
        raise HTTPException(status_code=400, detail="No tenant in context")
    return ctx


async def db_session(
    tenant: TenantContext = Depends(current_tenant),
) -> AsyncIterator[AsyncSession]:
    async with tenant_session(tenant.slug) as session:
        yield session


def current_principal(
    tenant: TenantContext = Depends(current_tenant),
    authorization: str | None = Header(default=None),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        principal = decode_token(token)
    except Exception as exc:  # pyjwt raises many subclasses
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if principal.tenant != tenant.slug:
        raise HTTPException(status_code=403, detail="Token/tenant mismatch")
    return principal


def require_permission(code: str):
    """Dependency factory: 403 unless the principal holds ``code`` (or is admin)."""

    def guard(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.is_admin:
            # Full permission resolution hits the DB; the admin shortcut covers
            # the bootstrap path. Module routers can load roles when needed.
            raise HTTPException(status_code=403, detail=f"Requires permission '{code}'")
        return principal

    return guard
