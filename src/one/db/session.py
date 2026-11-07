"""Async engine + per-tenant session.

Schema-per-tenant is enforced here and nowhere else: a request resolves a
tenant, and every statement in that request runs against the tenant's schema
because we issue ``SET LOCAL search_path TO <tenant>, public`` on the
connection inside the transaction. ``SET LOCAL`` is scoped to the transaction,
so a pooled connection never leaks one tenant's search_path into another's
request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from one.config import get_settings

_settings = get_settings()

# One engine per process. Created lazily-enough (module import) but cheap; it
# does not open connections until first use, so importing this module in tests
# that never touch the DB is safe.
#
# NullPool (db_null_pool=True) is used in tests: each operation gets a fresh
# connection closed immediately after, so nothing leaks across the per-test
# event loops that pytest-asyncio and the TestClient create.
if _settings.db_null_pool:
    engine = create_async_engine(_settings.database_url, echo=_settings.db_echo, poolclass=NullPool)
else:
    engine = create_async_engine(
        _settings.database_url,
        echo=_settings.db_echo,
        pool_size=_settings.db_pool_size,
        max_overflow=_settings.db_max_overflow,
        pool_pre_ping=True,
    )

_sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def schema_for(tenant_slug: str) -> str:
    """Map a tenant slug to its Postgres schema name."""
    return f"{_settings.tenant_schema_prefix}{tenant_slug}"


def _quote_ident(ident: str) -> str:
    # tenant slugs are validated on creation (slugify), but quote defensively.
    return '"' + ident.replace('"', '""') + '"'


@asynccontextmanager
async def tenant_session(tenant_slug: str) -> AsyncIterator[AsyncSession]:
    """Yield a session bound to one tenant's schema for the whole transaction."""
    schema = schema_for(tenant_slug)
    async with _sessionmaker() as session:
        await session.execute(text(f"SET LOCAL search_path TO {_quote_ident(schema)}, public"))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def public_session() -> AsyncIterator[AsyncSession]:
    """Yield a session scoped to the public (tenant-registry) schema."""
    async with _sessionmaker() as session:
        await session.execute(text("SET LOCAL search_path TO public"))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
