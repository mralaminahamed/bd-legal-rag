"""Tests for LLM base protocols and call_with_retries."""

from __future__ import annotations

import pytest
from app.llm.base import (
    CompletionRequest,
    CompletionResult,
    LLMProvider,
    ProviderRejected,
    ProviderUnavailable,
    StreamingProvider,
    TokenUsage,
    call_with_retries,
)


def test_token_usage_total() -> None:
    u = TokenUsage(input_tokens=100, output_tokens=50)
    assert u.total_tokens == 150


def test_completion_request_defaults() -> None:
    r = CompletionRequest(system="sys", user="hi", max_tokens=512)
    assert r.temperature == 0.0


def test_provider_unavailable_is_exception() -> None:
    exc = ProviderUnavailable("timeout")
    assert isinstance(exc, Exception)
    assert str(exc) == "timeout"


def test_provider_rejected_is_exception() -> None:
    exc = ProviderRejected("content policy")
    assert isinstance(exc, Exception)


@pytest.mark.asyncio
async def test_call_with_retries_succeeds_first_attempt() -> None:
    calls: list[int] = []

    async def fn() -> str:
        calls.append(1)
        return "ok"

    result = await call_with_retries(fn, max_retries=3)
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_call_with_retries_retries_on_provider_unavailable() -> None:
    calls: list[int] = []

    async def fn() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ProviderUnavailable("503")
        return "recovered"

    result = await call_with_retries(fn, max_retries=3, base_delay=0.0)
    assert result == "recovered"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_call_with_retries_does_not_retry_rejected() -> None:
    calls: list[int] = []

    async def fn() -> str:
        calls.append(1)
        raise ProviderRejected("4xx")

    with pytest.raises(ProviderRejected):
        await call_with_retries(fn, max_retries=3, base_delay=0.0)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_call_with_retries_raises_after_max_retries() -> None:
    async def fn() -> str:
        raise ProviderUnavailable("always down")

    with pytest.raises(ProviderUnavailable):
        await call_with_retries(fn, max_retries=2, base_delay=0.0)


def test_llm_provider_is_runtime_checkable() -> None:
    class FakeProvider:
        async def complete(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult(
                text="hello",
                usage=TokenUsage(10, 5),
                model="fake",
            )

        @property
        def model(self) -> str:
            return "fake"

    assert isinstance(FakeProvider(), LLMProvider)


def test_streaming_provider_is_runtime_checkable() -> None:
    from collections.abc import AsyncIterator

    class FakeStreamer:
        async def complete(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult(text="", usage=TokenUsage(0, 0), model="fake")

        @property
        def model(self) -> str:
            return "fake"

        async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
            yield "tok"

    assert isinstance(FakeStreamer(), StreamingProvider)
