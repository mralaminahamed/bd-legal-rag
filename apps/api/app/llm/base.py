"""LLM provider protocols, shared types, and retry helper (architecture §2.5).

All generation back-ends implement ``LLMProvider`` (and optionally
``StreamingProvider``).  Nothing outside ``app/llm/`` imports concrete
provider classes — only these protocols.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ProviderUnavailable(Exception):  # noqa: N818  # name is an architectural contract (CLAUDE.md)
    """Provider temporarily unreachable (timeout, 5xx, network error)."""


class ProviderRejected(Exception):  # noqa: N818  # name is an architectural contract (CLAUDE.md)
    """Provider refused the request (4xx, content policy, invalid auth)."""


@dataclass(frozen=True)
class TokenUsage:
    """Token counts reported by the provider.

    Attributes:
        input_tokens: Tokens in the prompt.
        output_tokens: Tokens in the completion.
    """

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        """Sum of input and output tokens."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class CompletionRequest:
    """Input for a single generation call.

    Attributes:
        system: System prompt text (never contains the disclaimer).
        user: User message text.
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature (default 0.0 for deterministic output).
    """

    system: str
    user: str
    max_tokens: int
    temperature: float = 0.0


@dataclass(frozen=True)
class CompletionResult:
    """Output from a generation call.

    Attributes:
        text: Generated completion text.
        usage: Token usage reported by the provider.
        model: Provider model identifier used for this call.
    """

    text: str
    usage: TokenUsage
    model: str


@runtime_checkable
class LLMProvider(Protocol):
    """Async completion provider (architecture §2.5).

    Implementations must be thin: timeout, retry/backoff, structured errors.
    Caching, circuit breaking, citation handling, and guardrails belong in
    ``app/rag/generator.py``.
    """

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a full completion and return it.

        Args:
            request: The completion request.

        Returns:
            CompletionResult: The generated text and token usage.

        Raises:
            ProviderUnavailable: On transient errors (timeout, 5xx).
            ProviderRejected: On permanent errors (4xx, content policy).
        """
        ...

    @property
    def model(self) -> str:
        """Model identifier used by this provider instance."""
        ...


@runtime_checkable
class StreamingProvider(Protocol):
    """Extends LLMProvider with token-by-token streaming."""

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a full completion (non-streaming fallback)."""
        ...

    @property
    def model(self) -> str:
        """Model identifier used by this provider instance."""
        ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield text deltas as they arrive from the provider.

        Args:
            request: The completion request.

        Yields:
            str: Each text delta from the provider.

        Raises:
            ProviderUnavailable: On transient errors.
            ProviderRejected: On permanent errors.
        """
        ...


async def call_with_retries[T](
    coro_fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    base_delay: float = 1.0,
) -> T:
    """Call an async function with bounded exponential-backoff retry.

    Retries only on :class:`ProviderUnavailable`; :class:`ProviderRejected`
    propagates immediately.

    Args:
        coro_fn: Zero-argument async callable to call.
        max_retries: Maximum number of retries (0 = one attempt, no retries).
        base_delay: Base sleep seconds for exponential backoff.

    Returns:
        T: The return value of ``coro_fn`` on success.

    Raises:
        ProviderUnavailable: After all retries are exhausted.
        ProviderRejected: Immediately without retry.
    """
    last_exc: ProviderUnavailable | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except ProviderRejected:
            raise
        except ProviderUnavailable as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "provider_unavailable attempt=%d/%d delay=%.1fs err=%s",
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    exc,
                )
                if delay > 0:
                    await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
