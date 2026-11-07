"""Shared fixtures. Postgres-backed tests run only when ONE_TEST_DATABASE_URL is set."""

from __future__ import annotations

import os
import uuid

import pytest

TEST_DB = os.environ.get("ONE_TEST_DATABASE_URL")

# When a test DB is provided, point the app's engine at it before anything imports it.
if TEST_DB:
    os.environ["ONE_DATABASE_URL"] = TEST_DB
    os.environ["ONE_DB_NULL_POOL"] = "true"  # no connection reuse across per-test loops
    os.environ.setdefault("ONE_BASE_DOMAIN", "nettcom.io")
    os.environ.setdefault("ONE_JWT_SECRET", "test-secret-at-least-32-bytes-long-xx")


requires_db = pytest.mark.skipif(not TEST_DB, reason="ONE_TEST_DATABASE_URL not set")


@pytest.fixture
def tenant_slug() -> str:
    return "t" + uuid.uuid4().hex[:10]


@pytest.fixture
async def provisioned_tenant(tenant_slug):
    """Create a fresh tenant schema and tear it down after the test."""
    from sqlalchemy import text

    from one.db.migrate import migrate_public, migrate_tenant
    from one.db.session import engine, schema_for
    from one.tenancy.provisioning import create_tenant

    await migrate_public()
    await create_tenant(name=tenant_slug, slug=tenant_slug)
    await migrate_tenant(tenant_slug)
    yield tenant_slug
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_for(tenant_slug)}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenant WHERE slug = :s"), {"s": tenant_slug})
