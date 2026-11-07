"""Worker supervisor — runs one stream consumer per active tenant.

This is the entrypoint of the ``worker`` role. It discovers active tenants,
launches a ``run_consumer`` task for each, and periodically picks up newly
provisioned tenants. Consumers share a Redis consumer group per tenant, so
scaling the worker to N replicas spreads a message burst across them.
"""

from __future__ import annotations

import asyncio
import logging
import os

from one.comms.consumer import run_consumer
from one.tenancy.provisioning import list_tenant_slugs

log = logging.getLogger("one.worker")
REFRESH_SECONDS = 30


async def supervise() -> None:
    name = os.environ.get("HOSTNAME", "w1")
    running: dict[str, asyncio.Task] = {}
    log.info("Worker supervisor starting (consumer=%s)", name)
    while True:
        try:
            slugs = set(await list_tenant_slugs())
        except Exception:  # noqa: BLE001 - DB may blip; keep existing consumers alive
            slugs = set(running)
        # Start consumers for new tenants.
        for slug in slugs - set(running):
            running[slug] = asyncio.create_task(run_consumer(slug, consumer_name=name))
            log.info("Consuming tenant %s", slug)
        # Drop finished/crashed tasks so they restart next loop.
        for slug, task in list(running.items()):
            if task.done():
                running.pop(slug, None)
        await asyncio.sleep(REFRESH_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(supervise())


if __name__ == "__main__":
    main()
