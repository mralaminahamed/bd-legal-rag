"""Tests for concrete LLM providers (all external calls mocked)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.base import (
    CompletionRequest,
    CompletionResult,
    LLMProvider,
    ProviderRejected,
    ProviderUnavailable,
    StreamingProvider,
    TokenUsage,
)


# ──────────────────────────────── Anthropic ───────────────────────────────────

@pytest.mark.asyncio
async def test_anthropic_complete_returns_result() -> None:
    from app.llm.anthropic import AnthropicProvider

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="The answer is 42.")]
    mock_msg.usage.input_tokens = 10
    mock_msg.usage.output_tokens = 5
    mock_msg.model = "claude-sonnet-4-6"

    with patch("anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(return_value=mock_msg)
        provider = AnthropicProvider(api_key="sk-test", model="claude-sonnet-4-6", timeout=5.0, max_retries=0)
        req = CompletionRequest(system="sys", user="q", max_tokens=128)
        result = await provider.complete(req)

    assert result.text == "The answer is 42."
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5
    assert result.model == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_anthropic_timeout_raises_provider_unavailable() -> None:
    import anthropic

    from app.llm.anthropic import AnthropicProvider

    with patch("anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            side_effect=anthropic.APITimeoutError(request=MagicMock())
        )
        provider = AnthropicProvider(api_key="sk-test", model="claude-sonnet-4-6", timeout=5.0, max_retries=0)
        req = CompletionRequest(system="sys", user="q", max_tokens=128)
        with pytest.raises(ProviderUnavailable):
            await provider.complete(req)


@pytest.mark.asyncio
async def test_anthropic_auth_error_raises_provider_rejected() -> None:
    import anthropic

    from app.llm.anthropic import AnthropicProvider

    with patch("anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            side_effect=anthropic.AuthenticationError(
                message="invalid key", response=MagicMock(), body={}
            )
        )
        provider = AnthropicProvider(api_key="bad-key", model="claude-sonnet-4-6", timeout=5.0, max_retries=0)
        req = CompletionRequest(system="sys", user="q", max_tokens=128)
        with pytest.raises(ProviderRejected):
            await provider.complete(req)


@pytest.mark.asyncio
async def test_anthropic_implements_streaming_provider() -> None:
    from app.llm.anthropic import AnthropicProvider

    provider = AnthropicProvider(api_key="sk-test", model="claude-sonnet-4-6", timeout=5.0, max_retries=0)
    assert isinstance(provider, StreamingProvider)


@pytest.mark.asyncio
async def test_anthropic_stream_yields_deltas() -> None:
    from app.llm.anthropic import AnthropicProvider

    async def fake_stream_ctx() -> AsyncIterator[MagicMock]:
        for delta in ["Hello", " world"]:
            ev = MagicMock()
            ev.type = "content_block_delta"
            ev.delta = MagicMock()
            ev.delta.type = "text_delta"
            ev.delta.text = delta
            yield ev

    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=fake_stream_ctx())
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    with patch("anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.stream.return_value = mock_stream
        provider = AnthropicProvider(api_key="sk-test", model="claude-sonnet-4-6", timeout=5.0, max_retries=0)
        req = CompletionRequest(system="sys", user="q", max_tokens=128)
        tokens: list[str] = []
        async for token in await provider.stream(req):
            tokens.append(token)

    assert tokens == ["Hello", " world"]


# ──────────────────────────────── OpenAI ──────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_complete_returns_result() -> None:
    from app.llm.openai import OpenAIProvider

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "OpenAI answer"
    mock_resp.usage.prompt_tokens = 8
    mock_resp.usage.completion_tokens = 3
    mock_resp.model = "gpt-4o-mini"

    with patch("openai.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.create = AsyncMock(return_value=mock_resp)
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", timeout=5.0, max_retries=0)
        req = CompletionRequest(system="sys", user="q", max_tokens=128)
        result = await provider.complete(req)

    assert result.text == "OpenAI answer"
    assert result.usage.input_tokens == 8
    assert result.usage.output_tokens == 3


@pytest.mark.asyncio
async def test_openai_timeout_raises_provider_unavailable() -> None:
    import openai as _openai

    from app.llm.openai import OpenAIProvider

    with patch("openai.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.create = AsyncMock(
            side_effect=_openai.APITimeoutError(request=MagicMock())
        )
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", timeout=5.0, max_retries=0)
        with pytest.raises(ProviderUnavailable):
            await provider.complete(CompletionRequest(system="s", user="u", max_tokens=128))


@pytest.mark.asyncio
async def test_openai_auth_error_raises_provider_rejected() -> None:
    import openai as _openai

    from app.llm.openai import OpenAIProvider

    with patch("openai.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.create = AsyncMock(
            side_effect=_openai.AuthenticationError(
                message="bad key", response=MagicMock(), body={}
            )
        )
        provider = OpenAIProvider(api_key="bad", model="gpt-4o-mini", timeout=5.0, max_retries=0)
        with pytest.raises(ProviderRejected):
            await provider.complete(CompletionRequest(system="s", user="u", max_tokens=128))


# ──────────────────────────────── Ollama ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_complete_returns_result() -> None:
    from app.llm.ollama import OllamaProvider

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": "Ollama answer"},
        "prompt_eval_count": 12,
        "eval_count": 6,
        "model": "llama3.2",
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockHTTP:
        MockHTTP.return_value.__aenter__ = AsyncMock(return_value=MockHTTP.return_value)
        MockHTTP.return_value.__aexit__ = AsyncMock(return_value=False)
        MockHTTP.return_value.post = AsyncMock(return_value=mock_resp)
        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2", timeout=5.0, max_retries=0)
        req = CompletionRequest(system="sys", user="q", max_tokens=128)
        result = await provider.complete(req)

    assert result.text == "Ollama answer"
    assert result.model == "llama3.2"


@pytest.mark.asyncio
async def test_ollama_connection_error_raises_provider_unavailable() -> None:
    import httpx

    from app.llm.ollama import OllamaProvider

    with patch("httpx.AsyncClient") as MockHTTP:
        MockHTTP.return_value.__aenter__ = AsyncMock(return_value=MockHTTP.return_value)
        MockHTTP.return_value.__aexit__ = AsyncMock(return_value=False)
        MockHTTP.return_value.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2", timeout=5.0, max_retries=0)
        with pytest.raises(ProviderUnavailable):
            await provider.complete(CompletionRequest(system="s", user="u", max_tokens=128))
