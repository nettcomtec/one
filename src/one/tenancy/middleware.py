"""Resolve the tenant for each request.

Resolution order:
1. ``X-Tenant`` header (explicit; handy for API clients and the AI worker).
2. Subdomain of the base domain: ``<slug>.nettcomone.com``.

The resolved tenant is validated against the registry and stashed in the
request state and the ContextVar. Unknown/inactive tenants → 404.
"""

from __future__ import annotations

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from one.config import get_settings
from one.db.session import public_session
from one.tenancy.context import TenantContext, set_current_tenant
from one.tenancy.models import Tenant

_settings = get_settings()

# Paths that must work without a tenant (health, docs, tenant admin).
_TENANTLESS_PREFIXES = ("/healthz", "/readyz", "/docs", "/openapi.json", "/redoc", "/_admin")
_TENANTLESS_EXACT = ("/favicon.ico",)


def _apex_html() -> str:
    return (
        '<!doctype html><meta charset="utf-8"><title>Nettcom ONE</title>'
        '<body style="font-family:system-ui;max-width:560px;margin:80px auto;color:#15171C">'
        "<h1>Nettcom ONE</h1><p style='color:#6B7280'>Acesse pelo endereço do seu workspace: "
        f"<code>&lt;seu-workspace&gt;.{_settings.base_domain}</code></p></body>"
    )


def _slug_from_host(host: str) -> str | None:
    host = host.split(":")[0]
    suffix = "." + _settings.base_domain
    if host.endswith(suffix):
        sub = host[: -len(suffix)]
        return sub or None
    return None


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _TENANTLESS_EXACT or any(path.startswith(p) for p in _TENANTLESS_PREFIXES):
            return await call_next(request)

        slug = request.headers.get(_settings.tenant_header) or _slug_from_host(
            request.headers.get("host", "")
        )
        if not slug:
            # Apex / no subdomain: show a friendly hint instead of a raw 400.
            if request.url.path == "/":
                return HTMLResponse(_apex_html(), status_code=200)
            return JSONResponse({"detail": "Tenant not specified"}, status_code=400)

        async with public_session() as session:
            tenant = await session.scalar(
                select(Tenant).where(Tenant.slug == slug, Tenant.is_active.is_(True))
            )
        if tenant is None:
            return JSONResponse({"detail": f"Unknown tenant '{slug}'"}, status_code=404)

        ctx = TenantContext(slug=tenant.slug, tenant_id=str(tenant.id))
        set_current_tenant(ctx)
        request.state.tenant = ctx
        return await call_next(request)
