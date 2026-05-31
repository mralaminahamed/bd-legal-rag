"""OpenAI generation provider (architecture §2.5).

Implements ``LLMProvider`` for the OpenAI Chat Completions API.
This module is intentionally thin: timeout, bounded retry with backoff, and
structured error mapping only.  Caching, circuit breaking, guardrails, and
citation handling belong in ``app/rag/generator.py``.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging

import openai

from app.llm.base import (
    CompletionRequest,
    CompletionResult,
    ProviderRejected,
    ProviderUnavailable,
    TokenUsage,
    call_with_retries,
)

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI Chat Completions provider implementing LLMProvider.

    Args:
        api_key: OpenAI API key (never logged).
        model: Model identifier (e.g. ``"gpt-4o-mini"``).
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
        self._client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_retries = max_retries

    @property
    def model(self) -> str:
        """Model identifier used by this provider instance."""
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a full completion via the OpenAI Chat Completions API.

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
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    messages=[
                        {"role": "system", "content": request.system},
                        {"role": "user", "content": request.user},
                    ],
                )
            except openai.APITimeoutError as exc:
                raise ProviderUnavailable(f"openai timeout: {exc}") from exc
            except openai.RateLimitError as exc:
                raise ProviderUnavailable(f"openai rate_limit: {exc}") from exc
            except openai.APIConnectionError as exc:
                raise ProviderUnavailable(f"openai connection: {exc}") from exc
            except openai.AuthenticationError as exc:
                raise ProviderRejected(f"openai rejected: {exc}") from exc
            except openai.BadRequestError as exc:
                raise ProviderRejected(f"openai bad_request: {exc}") from exc

            text = resp.choices[0].message.content or ""
            usage = resp.usage
            return CompletionResult(
                text=text,
                usage=TokenUsage(
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                ),
                model=resp.model,
            )

        return await call_with_retries(_call, max_retries=self._max_retries)
