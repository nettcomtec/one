"""Schema bootstrap / migration.

Fase 0 uses SQLAlchemy metadata to create structures deterministically:

* ``migrate_public`` — ensure the ``public`` tenant registry exists.
* ``migrate_tenant`` — create every business table inside one tenant schema.
* ``migrate_all``    — public, then every active tenant.

This runs as the ``migrate`` process role on deploy. When models start to
evolve in production, this is the seam where Alembic (with per-schema
``version_table_schema``) takes over; the metadata stays the source of truth.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from one.db.base import PublicBase, TenantBase
from one.db.session import engine, schema_for
from one.identity import models as _identity  # noqa: F401
from one.ledger import models as _ledger  # noqa: F401
from one.sequences import models as _sequences  # noqa: F401

# Import model modules so their tables are attached to the metadata.
from one.tenancy import models as _tenancy  # noqa: F401


async def migrate_public() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        await conn.run_sync(PublicBase.metadata.create_all)


async def migrate_tenant(slug: str) -> None:
    schema = schema_for(slug)
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(f'SET search_path TO "{schema}", public'))

        def _create(sync_conn):
            TenantBase.metadata.create_all(bind=sync_conn)

        await conn.run_sync(_create)


async def migrate_all() -> None:
    await migrate_public()
    # Imported lazily to avoid a cycle at module import time.
    from one.tenancy.provisioning import list_tenant_slugs

    for slug in await list_tenant_slugs():
        await migrate_tenant(slug)


def main() -> None:
    asyncio.run(migrate_all())


if __name__ == "__main__":
    main()
