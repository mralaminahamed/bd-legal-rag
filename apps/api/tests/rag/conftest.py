"""Test fixtures for the rag package.

Flushes response-cache keys between generator tests so that a cached result
from one test cannot bleed into a subsequent test that expects a different
code path (fail-open, circuit-breaker, guardrails, etc.).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest


@pytest.fixture(autouse=True)
async def _flush_response_cache() -> AsyncIterator[None]:
    """Delete all ``response:*`` keys from Redis before and after each test.

    Prevents cross-test cache contamination when a real Redis is running
    (e.g. via the local Docker Compose stack).  The fixture is a no-op when
    Redis is unreachable.

    Yields:
        None: Control to the test body.
    """
    async def _flush() -> None:
        try:
            from app.db.redis import get_redis

            redis = get_redis()
            keys = await redis.keys("response:*")
            if keys:
                await redis.delete(*keys)
            await redis.aclose()
        except Exception:
            pass  # Redis not available — nothing to flush

    await _flush()
    yield
    await _flush()
