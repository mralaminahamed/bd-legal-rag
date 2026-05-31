"""Async Redis client management.

Owns the process-wide async Redis client used for the response cache, rate
limiter, LLM-provider override store, and Celery broker. The client
multiplexes over a connection pool; it is created once and shared.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import cast

from redis.asyncio import Redis

from app.config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """Return the process-wide async Redis client.

    Built once and memoised so the underlying connection pool is shared.
    Decoded responses are returned as ``str`` for ergonomic cache and counter
    access.

    Returns:
        Redis: The shared async Redis client.
    """
    settings = get_settings()
    return cast(Redis, Redis.from_url(str(settings.redis_dsn), decode_responses=True))


async def close_redis() -> None:
    """Close the Redis client and release its connection pool.

    Called on application shutdown.
    """
    await get_redis().aclose()
