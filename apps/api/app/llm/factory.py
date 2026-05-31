"""Config-driven LLM provider factory (architecture §2.5).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from app.config import ProviderName, Settings
from app.llm.base import LLMProvider


def create_provider(
    settings: Settings,
    *,
    provider_name: ProviderName | None = None,
) -> LLMProvider:
    """Resolve and instantiate an LLM provider from configuration.

    Args:
        settings: Application settings.
        provider_name: Override the default provider name.

    Returns:
        LLMProvider: A ready-to-use provider instance.

    Raises:
        ValueError: If the provider name is not recognised.
        ValueError: If required credentials are absent.
    """
    name: ProviderName = provider_name or settings.default_provider

    if name == "anthropic":
        from app.llm.anthropic import AnthropicProvider

        if settings.anthropic_api_key is None:
            raise ValueError("BDRAG_ANTHROPIC_API_KEY is required for the anthropic provider")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.anthropic_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if name == "openai":
        from app.llm.openai import OpenAIProvider

        if settings.openai_api_key is None:
            raise ValueError("BDRAG_OPENAI_API_KEY is required for the openai provider")
        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if name == "ollama":
        from app.llm.ollama import OllamaProvider

        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    raise ValueError(f"unknown provider: {name!r}")
