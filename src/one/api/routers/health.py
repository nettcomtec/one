"""Liveness and readiness. Tenantless (see TenantMiddleware allowlist)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import text

from one import __version__
from one.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "db": "up"}
    except Exception as exc:  # pragma: no cover - depends on live DB
        return {"status": "degraded", "db": "down", "error": str(exc)}


_ROOT_HTML = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Nettcom ONE</title>
<body style="font-family:system-ui;max-width:640px;margin:80px auto;color:#15171C;line-height:1.5">
<h1 style="margin:0 0 4px">Nettcom ONE
  <small style="font-weight:400;color:#6B7280">v{version}</small></h1>
<p style="color:#6B7280;margin:0 0 24px">API no ar. O front chega em breve.</p>
<ul>
<li><a href="/docs">Documentação da API (Swagger)</a> —
  em <em>Authorize</em>, informe o token e o slug do tenant.</li>
<li><a href="/readyz">Status do banco</a></li>
</ul>
<p style="color:#6B7280;font-size:14px">Cada cliente é um tenant: acesse por
  <code>&lt;slug&gt;.&lt;domínio&gt;</code> ou envie o header <code>X-Tenant</code>.</p>
</body></html>"""


@router.get("/", include_in_schema=False)
async def root() -> HTMLResponse:
    return HTMLResponse(_ROOT_HTML.format(version=__version__))


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)
