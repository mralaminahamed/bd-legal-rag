"""Content-hash Redis response cache (architecture §2.5).

Cache key: ``sha256(normalised_query | sorted_chunk_ids | as_of_date | model
| prompt_version | reranker_version)``.  Changing ``as_of_date`` or
``reranker_version`` invalidates the key — both influence the answer.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any  # redis client types vary by version; no universal stub

logger = logging.getLogger(__name__)


def cache_key(
    query: str,
    chunk_ids: list[str],
    as_of_date: str,
    model: str,
    prompt_version: str,
    reranker_version: str,
) -> str:
    """Compute a deterministic SHA-256 cache key.

    Chunk IDs are sorted before hashing so insertion order does not matter.

    Args:
        query: The user query (whitespace-normalised, lowercased).
        chunk_ids: Chunk UUIDs returned by retrieval.
        as_of_date: Effective date string (YYYY-MM-DD).
        model: LLM model identifier.
        prompt_version: Active prompt version string.
        reranker_version: Active reranker model string.

    Returns:
        str: ``response:<hex-sha256>`` cache key.
    """
    normalised_query = " ".join(query.strip().lower().split())
    ordered_ids = "|".join(sorted(chunk_ids))
    payload = (
        f"{normalised_query}|{ordered_ids}|{as_of_date}|{model}|{prompt_version}|{reranker_version}"
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"response:{digest}"


class ResponseCache:
    """Thin async Redis wrapper for response caching.

    Args:
        redis: Async Redis client.
        ttl_seconds: Time-to-live for cached entries.
    """

    def __init__(self, redis: Any, ttl_seconds: int) -> None:
        """Initialize the response cache with Redis client and TTL.

        Args:
            redis: Async Redis client.
            ttl_seconds: Time-to-live for cached entries in seconds.
        """
        self._redis = redis
        self._ttl = ttl_seconds

    async def get(self, key: str) -> str | None:
        """Return a cached response or ``None`` on miss.

        Args:
            key: Cache key from :func:`cache_key`.

        Returns:
            str | None: Cached response string, or ``None`` on miss.
        """
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    async def set(self, key: str, value: str) -> None:
        """Store a response in Redis with the configured TTL.

        Args:
            key: Cache key from :func:`cache_key`.
            value: Response string to cache.
        """
        await self._redis.setex(key, self._ttl, value)
