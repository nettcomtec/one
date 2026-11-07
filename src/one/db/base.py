"""Declarative base and shared metadata conventions.

Two logical namespaces share one SQLAlchemy metadata but map to different
Postgres schemas at runtime:

* ``public``  — the tenant registry (see tenancy.models.Tenant). Tables that
  subclass :class:`PublicBase` are pinned to ``public``.
* ``<tenant>`` — every business table (ledger, identity, sequences, ...).
  Tables that subclass :class:`TenantBase` carry NO schema; the active schema
  is chosen per-request via ``SET LOCAL search_path`` (see db.session).
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names → clean Alembic autogenerate diffs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class TenantBase(DeclarativeBase):
    """Business tables. Schema is resolved at runtime via search_path."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class PublicBase(DeclarativeBase):
    """Global tables, pinned to the ``public`` schema."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION, schema="public")
