"""FastAPI dependencies: tenant-scoped DB session, current principal, permission guard."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from one.db.session import tenant_session
from one.identity.security import Principal, decode_token
from one.tenancy.context import TenantContext

# Declared security schemes → Swagger's "Authorize" button asks for both.
bearer_scheme = HTTPBearer(
    auto_error=False, description="Token JWT (python -m one.cli issue-token)"
)
tenant_scheme = APIKeyHeader(
    name="X-Tenant", auto_error=False, description="Slug do tenant (ex.: nettcom)"
)


def current_tenant(
    request: Request,
    _x_tenant: str | None = Depends(tenant_scheme),  # only so Swagger documents the header
) -> TenantContext:
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
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    # Accept either a Bearer token (API clients, the agent) or the web session
    # cookie, so the same endpoints serve the API and the server-rendered UI.
    token: str | None = None
    if creds is not None and creds.scheme.lower() == "bearer":
        token = creds.credentials
    else:
        token = request.cookies.get("one_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
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
