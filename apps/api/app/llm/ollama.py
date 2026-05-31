"""Ollama local LLM provider (architecture §2.5).

Implements ``LLMProvider`` for a locally running Ollama instance via its
``/api/chat`` HTTP endpoint.  This module is intentionally thin: timeout,
bounded retry with backoff, and structured error mapping only.  Caching,
circuit breaking, guardrails, and citation handling belong in
``app/rag/generator.py``.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging

import httpx

from app.llm.base import (
    CompletionRequest,
    CompletionResult,
    ProviderRejected,
    ProviderUnavailable,
    TokenUsage,
    call_with_retries,
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Ollama local LLM provider implementing LLMProvider.

    Communicates with an Ollama instance over HTTP using the ``/api/chat``
    endpoint in non-streaming mode.

    Args:
        base_url: Base URL of the Ollama server (e.g. ``"http://localhost:11434"``).
        model: Model name to use (e.g. ``"llama3.2"``).
        timeout: Per-call timeout in seconds.
        max_retries: Maximum number of retries on transient failures (0 = no retry).
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        """Initialise the provider with server URL and call parameters."""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def model(self) -> str:
        """Model identifier used by this provider instance."""
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a full completion via the Ollama /api/chat endpoint.

        Args:
            request: The completion request containing system prompt, user message,
                and generation parameters.

        Returns:
            CompletionResult: The generated text, token usage, and model identifier.

        Raises:
            ProviderUnavailable: On transient errors (timeout, connection error, 5xx).
            ProviderRejected: On permanent errors (4xx responses).
        """

        async def _call() -> CompletionResult:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        f"{self._base_url}/api/chat",
                        json={
                            "model": self._model,
                            "messages": [
                                {"role": "system", "content": request.system},
                                {"role": "user", "content": request.user},
                            ],
                            "stream": False,
                            "options": {
                                "num_predict": request.max_tokens,
                                "temperature": request.temperature,
                            },
                        },
                    )
                    resp.raise_for_status()
            except httpx.TimeoutException as exc:
                raise ProviderUnavailable(f"ollama timeout: {exc}") from exc
            except httpx.ConnectError as exc:
                raise ProviderUnavailable(f"ollama connection: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise ProviderRejected(
                        f"ollama rejected ({exc.response.status_code}): {exc}"
                    ) from exc
                raise ProviderUnavailable(
                    f"ollama server error ({exc.response.status_code}): {exc}"
                ) from exc

            data: dict[str, object] = resp.json()
            raw_message = data.get("message", {})
            text: str
            if isinstance(raw_message, dict):
                raw_content = raw_message.get("content", "")
                text = str(raw_content) if raw_content else ""
            else:
                text = ""
            model_name = str(data.get("model", self._model))
            raw_prompt = data.get("prompt_eval_count", 0)
            raw_eval = data.get("eval_count", 0)
            prompt_eval_count = int(raw_prompt) if isinstance(raw_prompt, int) else 0
            eval_count = int(raw_eval) if isinstance(raw_eval, int) else 0

            return CompletionResult(
                text=str(text),
                usage=TokenUsage(
                    input_tokens=prompt_eval_count,
                    output_tokens=eval_count,
                ),
                model=model_name,
            )

        return await call_with_retries(_call, max_retries=self._max_retries)
