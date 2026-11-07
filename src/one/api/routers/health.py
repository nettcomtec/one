"""Liveness and readiness. Tenantless (see TenantMiddleware allowlist)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy import text

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


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)
