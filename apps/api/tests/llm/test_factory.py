"""Tests for config-driven LLM provider factory."""

from __future__ import annotations

import pytest
from app.config import Settings


def _settings(**overrides: str) -> Settings:
    base: dict[str, str] = {
        "anthropic_api_key": "sk-ant-test",
        "openai_api_key": "sk-oai-test",
    }
    base.update(overrides)
    return Settings.model_validate(base)


def test_factory_creates_anthropic_provider() -> None:
    from app.llm.anthropic import AnthropicProvider
    from app.llm.factory import create_provider

    s = _settings(default_provider="anthropic")
    provider = create_provider(s)
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == s.anthropic_model


def test_factory_creates_openai_provider() -> None:
    from app.llm.factory import create_provider
    from app.llm.openai import OpenAIProvider

    s = _settings(default_provider="openai")
    provider = create_provider(s, provider_name="openai")
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == s.openai_model


def test_factory_creates_ollama_provider() -> None:
    from app.llm.factory import create_provider
    from app.llm.ollama import OllamaProvider

    s = _settings()
    provider = create_provider(s, provider_name="ollama")
    assert isinstance(provider, OllamaProvider)
    assert provider.model == s.ollama_model


def test_factory_unknown_name_raises() -> None:
    from app.llm.factory import create_provider

    s = _settings()
    with pytest.raises(ValueError, match="unknown provider"):
        create_provider(s, provider_name="nonexistent")  # type: ignore[arg-type]
