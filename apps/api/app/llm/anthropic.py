"""Anthropic/Claude generation provider (architecture §2.5).

Implements ``LLMProvider`` and ``StreamingProvider`` for the Anthropic API.
This module is intentionally thin: timeout, bounded retry with backoff, and
structured error mapping only.  Caching, circuit breaking, guardrails, and
citation handling belong in ``app/rag/generator.py``.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import anthropic

from app.llm.base import (
    CompletionRequest,
    CompletionResult,
    ProviderRejected,
    ProviderUnavailable,
    TokenUsage,
    call_with_retries,
)

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic Claude provider implementing LLMProvider + StreamingProvider.

    Args:
        api_key: Anthropic API key (never logged).
        model: Model identifier (e.g. ``"claude-sonnet-4-6"``).
        timeout: Per-call timeout in seconds.
        max_retries: Maximum number of retries on transient failures (0 = no retry).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        """Initialise the provider with credentials and call parameters."""
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_retries = max_retries

    @property
    def model(self) -> str:
        """Model identifier used by this provider instance."""
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a full completion and return it.

        Args:
            request: The completion request containing system prompt, user message,
                and generation parameters.

        Returns:
            CompletionResult: The generated text, token usage, and model identifier.

        Raises:
            ProviderUnavailable: On transient errors (timeout, rate limit, connection).
            ProviderRejected: On permanent errors (auth failure, bad request).
        """

        async def _call() -> CompletionResult:
            try:
                msg = await self._client.messages.create(
                    model=self._model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    system=request.system,
                    messages=[{"role": "user", "content": request.user}],
                )
            except anthropic.APITimeoutError as exc:
                raise ProviderUnavailable(f"anthropic timeout: {exc}") from exc
            except anthropic.RateLimitError as exc:
                raise ProviderUnavailable(f"anthropic rate_limit: {exc}") from exc
            except anthropic.APIConnectionError as exc:
                raise ProviderUnavailable(f"anthropic connection: {exc}") from exc
            except (
                anthropic.AuthenticationError,
                anthropic.PermissionDeniedError,
            ) as exc:
                raise ProviderRejected(f"anthropic rejected: {exc}") from exc
            except anthropic.BadRequestError as exc:
                raise ProviderRejected(f"anthropic bad_request: {exc}") from exc

            text = "".join(
                block.text
                for block in msg.content
                if hasattr(block, "text")
            )
            return CompletionResult(
                text=text,
                usage=TokenUsage(
                    input_tokens=msg.usage.input_tokens,
                    output_tokens=msg.usage.output_tokens,
                ),
                model=msg.model,
            )

        return await call_with_retries(_call, max_retries=self._max_retries)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Return an async iterator that yields text deltas from the Anthropic streaming API.

        The caller must iterate the returned object:
        ``async for token in await provider.stream(req): ...``

        Args:
            request: The completion request containing system prompt, user message,
                and generation parameters.

        Returns:
            AsyncIterator[str]: An async iterator that yields each text delta.

        Raises:
            ProviderUnavailable: On transient errors (timeout, connection).
            ProviderRejected: On permanent errors (auth failure).
        """
        return self._stream_iter(request)

    async def _stream_iter(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Internal async generator that yields text deltas from Anthropic streaming.

        Args:
            request: The completion request.

        Yields:
            str: Each text delta from the streaming response.

        Raises:
            ProviderUnavailable: On transient errors (timeout, connection).
            ProviderRejected: On permanent errors (auth failure).
        """
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
            ) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        yield event.delta.text
        except anthropic.APITimeoutError as exc:
            raise ProviderUnavailable(f"anthropic stream timeout: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderUnavailable(f"anthropic stream rate_limit: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderUnavailable(f"anthropic stream connection: {exc}") from exc
        except (
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
        ) as exc:
            raise ProviderRejected(f"anthropic stream rejected: {exc}") from exc
        except anthropic.BadRequestError as exc:
            raise ProviderRejected(f"anthropic stream bad_request: {exc}") from exc
