"""Tests for Redis-based LLM runtime override."""

from __future__ import annotations

import pytest
from app.config import Settings


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "default_provider": "anthropic",
            "anthropic_model": "claude-sonnet-4-6",
        }
    )


@pytest.mark.asyncio
async def test_resolve_returns_env_defaults_when_no_override() -> None:
    from unittest.mock import AsyncMock

    from app.llm.runtime import resolve

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    s = _settings()
    cfg = await resolve(mock_redis, s)
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_resolve_returns_override_when_set() -> None:
    import json
    from unittest.mock import AsyncMock

    from app.llm.runtime import resolve

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(
        return_value=json.dumps({"provider": "openai", "model": "gpt-4o-mini"})
    )
    s = _settings()
    cfg = await resolve(mock_redis, s)
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_resolve_falls_back_on_malformed_json() -> None:
    from unittest.mock import AsyncMock

    from app.llm.runtime import resolve

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="{invalid json}")
    s = _settings()
    cfg = await resolve(mock_redis, s)
    assert cfg.provider == s.default_provider
    assert cfg.model == s.anthropic_model


@pytest.mark.asyncio
async def test_set_and_clear_override() -> None:
    from unittest.mock import MagicMock

    from app.llm.runtime import clear_override, get_override, set_override

    captured: dict[str, object] = {}

    async def fake_set(key: str, value: str) -> None:
        captured[key] = value

    async def fake_delete(*keys: str) -> None:
        for k in keys:
            captured.pop(k, None)

    async def fake_get(key: str) -> str | None:
        return captured.get(key)  # type: ignore[return-value]

    mock_redis = MagicMock()
    mock_redis.set = fake_set
    mock_redis.delete = fake_delete
    mock_redis.get = fake_get

    await set_override(mock_redis, provider="openai", model="gpt-4o-mini")
    override = await get_override(mock_redis)
    assert override is not None
    assert override.provider == "openai"

    await clear_override(mock_redis)
    assert await get_override(mock_redis) is None
