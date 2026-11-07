"""arq worker — async job queue backed by Redis.

Runs the same image as the API with ``ONE_ROLE=worker``. Long-running and
scheduled work (fiscal transmission, recurring billing, the lead miner poll)
lands here. A trivial task is included so the worker boots and is testable.
"""

from __future__ import annotations

from arq.connections import RedisSettings

from one.config import get_settings

_settings = get_settings()


async def ping(ctx, value: str = "pong") -> str:
    return value


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    # cron_jobs = [...]  # recurring billing, fiscal polling, lead miner — added per module
