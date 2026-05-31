"""Redis-based LLM provider/model runtime override (architecture §2.5).

Allows ops to switch the active provider/model without a restart by writing
to the ``llm:override`` Redis key. Falls back to env-configured defaults on
absent or malformed keys.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any  # redis client types vary by version; no universal stub

from app.config import ProviderName, Settings

logger = logging.getLogger(__name__)

_OVERRIDE_KEY = "llm:override"


@dataclass(frozen=True)
class EffectiveLLMConfig:
    """Resolved provider and model for a generation call.

    Attributes:
        provider: Resolved provider name.
        model: Resolved model identifier.
    """

    provider: ProviderName
    model: str


async def resolve(redis: Any, settings: Settings) -> EffectiveLLMConfig:
    """Return the effective provider/model, honouring any Redis override.

    Args:
        redis: Async Redis client.
        settings: Application settings (fallback values).

    Returns:
        EffectiveLLMConfig: The resolved provider and model.
    """
    raw = await redis.get(_OVERRIDE_KEY)
    if raw is not None:
        try:
            data = json.loads(raw)
            provider: ProviderName = data["provider"]
            model: str = data["model"]
            return EffectiveLLMConfig(provider=provider, model=model)
        except Exception as exc:
            logger.warning("malformed llm:override key, falling back to env: %s", exc)

    model_map: dict[ProviderName, str] = {
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
        "ollama": settings.ollama_model,
    }
    return EffectiveLLMConfig(
        provider=settings.default_provider,
        model=model_map[settings.default_provider],
    )


async def set_override(redis: Any, *, provider: ProviderName, model: str) -> None:
    """Write a provider/model override to Redis.

    Args:
        redis: Async Redis client.
        provider: Provider name to override to.
        model: Model identifier to override to.
    """
    await redis.set(_OVERRIDE_KEY, json.dumps({"provider": provider, "model": model}))


async def clear_override(redis: Any) -> None:
    """Remove the Redis override key, reverting to env defaults.

    Args:
        redis: Async Redis client.
    """
    await redis.delete(_OVERRIDE_KEY)


async def get_override(redis: Any) -> EffectiveLLMConfig | None:
    """Return the current override, or ``None`` if none is set.

    Args:
        redis: Async Redis client.

    Returns:
        EffectiveLLMConfig | None: The override or ``None``.
    """
    raw = await redis.get(_OVERRIDE_KEY)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return EffectiveLLMConfig(provider=data["provider"], model=data["model"])
    except Exception:
        return None
