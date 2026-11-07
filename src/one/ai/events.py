"""Domain event bus.

In-process pub/sub now, with an interface that swaps to Redis/arq later without
touching publishers. Modules emit events (``ledger.move.posted``,
``crm.lead.created``); agents and side-effects subscribe. Keeping publish/
subscribe behind this seam is what lets the AI layer react to the business
without the business knowing the AI exists.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

Handler = Callable[["Event"], Awaitable[None]]


@dataclass(frozen=True)
class Event:
    name: str
    tenant: str
    payload: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subs[event_name].append(handler)

    async def publish(self, event: Event) -> None:
        handlers = self._subs.get(event.name, [])
        if not handlers:
            return
        await asyncio.gather(*(h(event) for h in handlers))


bus = EventBus()
