"""Application configuration (12-factor: everything from env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONE_", env_file=".env", extra="ignore")

    # --- Runtime ---
    env: str = Field(default="dev", description="dev | staging | prod")
    debug: bool = Field(default=True)
    role: str = Field(default="api", description="Process role: api | worker | migrate")

    # --- Database (plain self-hosted Postgres; no Supabase stack) ---
    database_url: str = Field(
        default="postgresql+asyncpg://one:one@localhost:5432/one",
        description="Async SQLAlchemy URL. The 'public' schema holds the tenant registry.",
    )
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    db_echo: bool = Field(default=False)
    db_null_pool: bool = Field(default=False, description="NullPool (tests): no cross-loop reuse")

    # --- Redis (arq job queue / event bus transport) ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Auth (our own identity module issues/verifies JWTs) ---
    jwt_secret: str = Field(default="dev-insecure-change-me-min-32-bytes-ok")
    jwt_algorithm: str = Field(default="HS256")
    jwt_audience: str | None = Field(default=None)

    # --- Multi-tenancy ---
    tenant_schema_prefix: str = Field(default="t_", description="Prefix for each tenant's schema")
    tenant_header: str = Field(default="X-Tenant", description="Header carrying the tenant slug")
    base_domain: str = Field(
        default="nettcomone.com",
        description="Tenant resolved from subdomain: <slug>.<base_domain>",
    )

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
