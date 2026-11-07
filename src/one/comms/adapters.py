"""Channel adapters — turn a provider's raw webhook payload into InboundMessage.

Each channel type registers a parser. A payload may carry several messages, so a
parser returns a list. Adding a channel is adding a parser here; the rest of the
pipeline never changes. The ``generic`` parser accepts the already-normalized
shape and is what webchat, internal injection and tests use.
"""

from __future__ import annotations

from collections.abc import Callable

from one.comms.models import ChannelType, MessageType
from one.comms.service import InboundMessage

Parser = Callable[[str, dict], list[InboundMessage]]
_PARSERS: dict[ChannelType, Parser] = {}


def register(channel_type: ChannelType):
    def deco(fn: Parser) -> Parser:
        _PARSERS[channel_type] = fn
        return fn

    return deco


def parse(channel_type: ChannelType, channel_id: str, raw: dict) -> list[InboundMessage]:
    parser = _PARSERS.get(channel_type, _generic)
    return parser(channel_id, raw)


def _generic(channel_id: str, raw: dict) -> list[InboundMessage]:
    """Normalized passthrough: {address, body, type?, provider_message_id?, name?}."""
    return [
        InboundMessage(
            channel_id=channel_id,
            address=raw["address"],
            body=raw.get("body"),
            type=MessageType(raw.get("type", "text")),
            provider_message_id=raw.get("provider_message_id"),
            display_name=raw.get("name"),
            payload=raw.get("payload", {}),
        )
    ]


@register(ChannelType.whatsapp)
def _whatsapp_cloud(channel_id: str, raw: dict) -> list[InboundMessage]:
    """Parse a Meta WhatsApp Cloud API inbound webhook.

    Shape: entry[].changes[].value.{messages[], contacts[]}. Only the parts we
    need now; media/templates get fleshed out when that channel is wired for real.
    """
    out: list[InboundMessage] = []
    _TYPE = {
        "text": MessageType.text,
        "image": MessageType.image,
        "audio": MessageType.audio,
        "video": MessageType.video,
        "document": MessageType.file,
        "location": MessageType.location,
    }
    for entry in raw.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {
                c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])
            }
            for m in value.get("messages", []):
                wa_from = m.get("from")
                mtype = m.get("type", "text")
                body = m.get("text", {}).get("body") if mtype == "text" else None
                out.append(
                    InboundMessage(
                        channel_id=channel_id,
                        address=wa_from,
                        provider_message_id=m.get("id"),
                        type=_TYPE.get(mtype, MessageType.text),
                        body=body,
                        display_name=names.get(wa_from),
                        payload=m,
                    )
                )
    return out
