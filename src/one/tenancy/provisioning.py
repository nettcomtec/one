"""Create a new tenant: register it in public, create its schema, run tenant migrations.

The schema DDL is applied by the Alembic ``tenant_migrations`` environment so
that a freshly provisioned tenant and an existing one always converge to the
same structure. ``create_tenant`` registers the row and creates the empty
schema; ``migrate_all_tenants`` (run on deploy) brings every schema up to head.
"""

from __future__ import annotations

from slugify import slugify
from sqlalchemy import select, text

from one.db.session import public_session, schema_for
from one.tenancy.models import Tenant


class TenantExistsError(Exception):
    pass


async def create_tenant(name: str, slug: str | None = None, cnpj: str | None = None) -> dict:
    slug = slugify(slug or name, max_length=50, separator="_")
    async with public_session() as session:
        exists = await session.scalar(select(Tenant).where(Tenant.slug == slug))
        if exists is not None:
            raise TenantExistsError(f"Tenant '{slug}' already exists")

        tenant = Tenant(slug=slug, name=name, cnpj=cnpj)
        session.add(tenant)
        await session.flush()
        # Create the schema in the same transaction as the registry row.
        schema = schema_for(slug)
        await session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        result = {"id": str(tenant.id), "slug": slug, "name": name, "schema": schema}

    return result


async def list_tenant_slugs() -> list[str]:
    async with public_session() as session:
        rows = await session.scalars(select(Tenant.slug).where(Tenant.is_active.is_(True)))
        return list(rows)
