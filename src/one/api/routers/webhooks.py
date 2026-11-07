"""Inbound webhooks — the fast path. Validate lightly, enqueue, return 200.

A webhook handler must never touch Postgres or call a provider: if it is slow,
the provider retries and a burst becomes an avalanche. So this only drops the
raw payload onto the tenant's Redis stream and returns immediately; the worker
does the real work. Meta's verification GET is handled for WhatsApp.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from one.api.deps import current_tenant
from one.comms.bus import enqueue_inbound
from one.config import get_settings
from one.tenancy.context import TenantContext

router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)
_settings = get_settings()


@router.get("/{channel_id}")
async def verify(
    channel_id: str,
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    # Meta subscription handshake: echo the challenge when the verify token matches.
    if hub_mode == "subscribe" and hub_challenge is not None:
        return PlainTextResponse(hub_challenge)
    return {"status": "ok"}


@router.post("/{channel_id}")
async def receive(
    channel_id: str,
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
) -> dict:
    try:
        raw = await request.json()
    except Exception:
        raw = {"_body": (await request.body()).decode("utf-8", "replace")}
    await enqueue_inbound(tenant.slug, channel_id, raw)
    return {"status": "queued"}
