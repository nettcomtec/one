"""WebSocket gateway — the realtime delivery edge, a separate process role.

Agents' browsers hold a WebSocket here; the gateway subscribes to the tenant's
Redis pub/sub channel and forwards events (new message, status change) as they
happen. It runs as ``ONE_ROLE=gateway`` so thousands of long-lived sockets never
compete with the HTTP request pool of the ``api`` role, and it scales on its own.

Auth reuses the same JWT the rest of the app uses: the browser connects with
``/ws?token=<jwt>`` (or a cookie), the token's tenant must match the host's
tenant, and only then does the socket start receiving that tenant's events.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from one.comms.bus import subscribe_events
from one.identity.security import decode_token
from one.tenancy.middleware import _slug_from_host


def create_gateway() -> FastAPI:
    app = FastAPI(title="Nettcom ONE — Gateway")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "role": "gateway"}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
        # Resolve tenant from host (subdomain) and authenticate the token.
        host = websocket.headers.get("host", "")
        tenant = _slug_from_host(host) or websocket.query_params.get("tenant")
        tok = token or websocket.cookies.get("one_session")
        if not tenant or not tok:
            await websocket.close(code=4401)
            return
        try:
            principal = decode_token(tok)
        except Exception:
            await websocket.close(code=4401)
            return
        if principal.tenant != tenant:
            await websocket.close(code=4403)
            return

        await websocket.accept()
        await websocket.send_json({"kind": "ready", "tenant": tenant})

        async def pump() -> None:
            async for event in subscribe_events(tenant):
                await websocket.send_json(event)

        task = asyncio.create_task(pump())
        try:
            while True:  # keep the socket open; ignore inbound pings/text for now
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return app


app = create_gateway()
