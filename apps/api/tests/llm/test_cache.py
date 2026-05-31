"""Tests for content-hash response cache."""

from __future__ import annotations

import pytest


def test_cache_key_is_deterministic() -> None:
    from app.llm.cache import cache_key

    k1 = cache_key(
        query="test query",
        chunk_ids=["id-b", "id-a"],
        as_of_date="2026-01-01",
        model="claude-sonnet-4-6",
        prompt_version="v1",
        reranker_version="rerank-multilingual-v3.0",
    )
    k2 = cache_key(
        query="test query",
        chunk_ids=["id-a", "id-b"],  # different order — same key
        as_of_date="2026-01-01",
        model="claude-sonnet-4-6",
        prompt_version="v1",
        reranker_version="rerank-multilingual-v3.0",
    )
    assert k1 == k2
    assert k1.startswith("response:")
    assert len(k1) > 20


def test_cache_key_differs_on_date_change() -> None:
    from app.llm.cache import cache_key

    k1 = cache_key("q", ["x"], "2026-01-01", "m", "v1", "rv1")
    k2 = cache_key("q", ["x"], "2026-01-02", "m", "v1", "rv1")
    assert k1 != k2


def test_cache_key_differs_on_reranker_version_change() -> None:
    from app.llm.cache import cache_key

    k1 = cache_key("q", ["x"], "2026-01-01", "m", "v1", "rv1")
    k2 = cache_key("q", ["x"], "2026-01-01", "m", "v1", "rv2")
    assert k1 != k2


@pytest.mark.asyncio
async def test_response_cache_miss_returns_none() -> None:
    from unittest.mock import AsyncMock

    from app.llm.cache import ResponseCache

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    rc = ResponseCache(redis=mock_redis, ttl_seconds=86400)
    result = await rc.get("response:abc123")
    assert result is None


@pytest.mark.asyncio
async def test_response_cache_hit_returns_value() -> None:
    from unittest.mock import AsyncMock

    from app.llm.cache import ResponseCache

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"cached answer text")
    rc = ResponseCache(redis=mock_redis, ttl_seconds=86400)
    result = await rc.get("response:abc123")
    assert result == "cached answer text"


@pytest.mark.asyncio
async def test_response_cache_set_calls_redis_setex() -> None:
    from unittest.mock import AsyncMock

    from app.llm.cache import ResponseCache

    mock_redis = AsyncMock()
    rc = ResponseCache(redis=mock_redis, ttl_seconds=3600)
    await rc.set("response:abc123", "the answer")
    mock_redis.setex.assert_awaited_once_with("response:abc123", 3600, "the answer")
