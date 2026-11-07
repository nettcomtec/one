"""WhatsApp Cloud API (Meta) provider client — outbound send + webhook security.

The channel's ``config`` carries the credentials Meta issues:
    {"access_token": "...", "phone_number_id": "...", "app_secret": "...",
     "verify_token": "..."}
``phone_number_id`` is also mirrored on ``Channel.external_id``.

This module only talks to Meta's Graph API; persistence and status bookkeeping
live in comms.outbound so this stays a thin, unit-testable transport. The HTTP
client is injectable so tests run against a mock transport with no network.
"""

from __future__ import annotations

import hashlib
import hmac

import httpx

GRAPH = "https://graph.facebook.com/v21.0"


class WhatsAppError(RuntimeError):
    pass


class WhatsAppClient:
    def __init__(
        self, *, access_token: str, phone_number_id: str, client: httpx.AsyncClient | None = None
    ):
        self._token = access_token
        self._pnid = phone_number_id
        self._client = client

    async def _post(self, payload: dict) -> dict:
        url = f"{GRAPH}/{self._pnid}/messages"
        headers = {"Authorization": f"Bearer {self._token}"}
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                raise WhatsAppError(f"Meta {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        finally:
            if self._client is None:
                await client.aclose()

    @staticmethod
    def _first_message_id(data: dict) -> str | None:
        msgs = data.get("messages") or []
        return msgs[0].get("id") if msgs else None

    async def send_text(self, *, to: str, body: str) -> str | None:
        data = await self._post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"body": body},
            }
        )
        return self._first_message_id(data)

    async def send_template(
        self, *, to: str, name: str, language: str = "pt_BR", components: list | None = None
    ) -> str | None:
        template: dict = {"name": name, "language": {"code": language}}
        if components:
            template["components"] = components
        data = await self._post(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": template,
            }
        )
        return self._first_message_id(data)


def verify_signature(app_secret: str, raw_body: bytes, header: str | None) -> bool:
    """Validate Meta's X-Hub-Signature-256 header against the raw request body."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


def parse_statuses(raw: dict) -> list[dict]:
    """Extract delivery/read status updates from a Meta webhook payload.

    Returns [{"provider_message_id", "status"}], mapping Meta's status names to
    our MessageStatus values (sent/delivered/read/failed).
    """
    out: list[dict] = []
    _MAP = {"sent": "sent", "delivered": "delivered", "read": "read", "failed": "failed"}
    for entry in raw.get("entry", []):
        for change in entry.get("changes", []):
            for st in change.get("value", {}).get("statuses", []):
                mapped = _MAP.get(st.get("status"))
                if mapped and st.get("id"):
                    out.append({"provider_message_id": st["id"], "status": mapped})
    return out
