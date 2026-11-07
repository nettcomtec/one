"""JWT issue/verify. Our identity module owns auth — no external auth service.

The token carries the tenant slug and the user id so the API can resolve both
without an extra round-trip. In prod, rotate ``ONE_JWT_SECRET`` per environment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt

from one.config import get_settings

_settings = get_settings()


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant: str
    email: str | None = None
    is_admin: bool = False


def issue_token(principal: Principal, ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    payload = {
        "sub": principal.user_id,
        "tenant": principal.tenant,
        "email": principal.email,
        "adm": principal.is_admin,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if _settings.jwt_audience:
        payload["aud"] = _settings.jwt_audience
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> Principal:
    options = {"require": ["exp", "sub", "tenant"]}
    claims = jwt.decode(
        token,
        _settings.jwt_secret,
        algorithms=[_settings.jwt_algorithm],
        audience=_settings.jwt_audience,
        options=options,
    )
    return Principal(
        user_id=claims["sub"],
        tenant=claims["tenant"],
        email=claims.get("email"),
        is_admin=bool(claims.get("adm", False)),
    )
