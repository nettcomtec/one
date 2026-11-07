"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Importing tool modules registers their tools in the global registry.
from one.comms import tools as _comms_tools  # noqa: F401
from one.config import get_settings
from one.ledger import tools as _ledger_tools  # noqa: F401
from one.tenancy.middleware import TenantMiddleware

log = logging.getLogger("one.startup")

# Arbitrary fixed key for the migration advisory lock (so concurrent API
# replicas serialize the startup migration instead of racing it).
_MIGRATE_LOCK_KEY = 72_72_74


async def _run_startup_migrations() -> None:
    """Run migrations once, holding a Postgres advisory lock.

    With several API replicas, only one migrates at a time; the others block on
    the lock, then run the (idempotent) migration and continue. This replaces a
    separate ``migrate`` service, so an auto-deploy only has to update the image.
    """
    from sqlalchemy import text

    from one.db.migrate import migrate_all
    from one.db.session import engine

    async with engine.connect() as lock_conn:
        await lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATE_LOCK_KEY})
        await lock_conn.commit()
        try:
            await migrate_all()
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATE_LOCK_KEY})
            await lock_conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().migrate_on_startup:
        log.info("Running startup migrations ...")
        await _run_startup_migrations()
        log.info("Startup migrations done.")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Nettcom ONE",
        version="0.0.1",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(TenantMiddleware)

    from one.api import web
    from one.api.routers import ai, crm, health, inbox, inventory, ledger, webhooks

    app.include_router(health.router)
    app.include_router(ledger.router)
    app.include_router(ai.router)
    app.include_router(inbox.router)
    app.include_router(crm.router)
    app.include_router(inventory.router)
    app.include_router(webhooks.router)
    app.include_router(web.router)
    return app


app = create_app()
