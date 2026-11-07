"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from one.config import get_settings

# Importing tool modules registers their tools in the global registry.
from one.ledger import tools as _ledger_tools  # noqa: F401
from one.tenancy.middleware import TenantMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Nettcom ONE",
        version="0.0.1",
        debug=settings.debug,
    )
    app.add_middleware(TenantMiddleware)

    from one.api.routers import ai, health, ledger

    app.include_router(health.router)
    app.include_router(ledger.router)
    app.include_router(ai.router)
    return app


app = create_app()
