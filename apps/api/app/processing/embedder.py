"""Cohere multilingual embedder with input_type discipline (ADR-002, FR-PR-3).

EmbedInputType is a StrEnum whose values match the Cohere API input_type parameter.
Passing the wrong value silently halves retrieval quality, so CohereEmbedder.embed
requires the caller to supply input_type explicitly — no default, no fallback. Any
call that omits input_type is a type error caught by mypy --strict.

The convenience wrappers embed_documents and embed_query bake in the correct value
for their use case and are the intended callers for production code.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum

import cohere

logger = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 60.0


class EmbedInputType(StrEnum):
    """Cohere input_type discriminator for embed-multilingual-v3.0 (ADR-002).

    Documents are embedded at ingest time with SEARCH_DOCUMENT; queries are
    embedded at request time with SEARCH_QUERY. Mixing the two silently degrades
    retrieval quality — the embedder forbids calling embed without an explicit
    type (there is no default).
    """

    SEARCH_DOCUMENT = "search_document"
    SEARCH_QUERY = "search_query"


class CohereEmbedder:
    """Async Cohere embedder with batching, retry, and input_type enforcement.

    Attributes:
        _api_key: Cohere API credential.
        _model: Cohere embedding model name.
        _batch_size: Maximum texts per single Cohere embed call.
        _timeout: Per-call HTTP timeout in seconds.
        _max_retries: Maximum retry attempts on transient failures.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        batch_size: int,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialise the embedder.

        Args:
            api_key: Cohere API key.
            model: Embedding model name (e.g. "embed-multilingual-v3.0").
            batch_size: Maximum texts per single Cohere embed call (≤ 96).
            timeout: Per-call HTTP timeout in seconds.
            max_retries: Retry attempts on transient failures before re-raising.
        """
        self._api_key = api_key
        self._model = model
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_retries = max_retries

    async def embed(self, texts: list[str], input_type: EmbedInputType) -> list[list[float]]:
        """Embed a list of texts.

        input_type is required with no default. Omitting it is a type error
        caught by mypy --strict (ADR-002). Use embed_documents or embed_query
        to avoid specifying it at the call site.

        Texts are automatically batched at _batch_size; each batch is retried
        up to _max_retries times on transient errors with exponential backoff.

        Args:
            texts: Non-empty list of texts to embed.
            input_type: SEARCH_DOCUMENT at ingest time; SEARCH_QUERY at request
                time. Required, no default (ADR-002).

        Returns:
            list[list[float]]: One 1024-dimensional embedding vector per input
                text, in input order.

        Raises:
            ValueError: If texts is empty.
            Exception: Re-raised from Cohere after all retries are exhausted.
        """
        if not texts:
            raise ValueError("texts must be non-empty")

        client = cohere.AsyncClient(api_key=self._api_key, timeout=self._timeout)
        results: list[list[float]] = []

        async with client:
            for start in range(0, len(texts), self._batch_size):
                batch = texts[start : start + self._batch_size]
                vectors = await self._embed_batch_with_retry(client, batch, input_type)
                results.extend(vectors)

        return results

    async def _embed_batch_with_retry(
        self,
        client: cohere.AsyncClient,
        batch: list[str],
        input_type: EmbedInputType,
    ) -> list[list[float]]:
        """Embed one batch with exponential-backoff retry.

        Args:
            client: Active Cohere async client (inside context manager).
            batch: Texts to embed (≤ _batch_size).
            input_type: Document or query discriminator.

        Returns:
            list[list[float]]: One vector per text.

        Raises:
            Exception: Re-raised from Cohere after all retries are exhausted.
        """
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.embed(
                    texts=batch,
                    model=self._model,
                    input_type=input_type.value,
                    embedding_types=["float"],
                )
                # cohere >= 5.0: response.embeddings.float_ when embedding_types=["float"]
                raw = response.embeddings.float_  # type: ignore[union-attr]
                if raw is None:
                    raise ValueError("Cohere returned null float embeddings")
                return list(raw)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self._max_retries:
                    wait = min(2.0**attempt, _MAX_BACKOFF_SECONDS)
                    logger.warning(
                        "embed batch failed, retrying",
                        extra={
                            "attempt": attempt,
                            "wait_seconds": wait,
                            "error": str(exc),
                        },
                    )
                    await asyncio.sleep(wait)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("unreachable")  # pragma: no cover

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed texts as search documents (ingest time, search_document).

        Args:
            texts: Document texts to embed.

        Returns:
            list[list[float]]: One 1024-dimensional vector per document.
        """
        return await self.embed(texts, EmbedInputType.SEARCH_DOCUMENT)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (request time, search_query).

        Args:
            text: The query text.

        Returns:
            list[float]: A 1024-dimensional embedding vector.
        """
        vectors = await self.embed([text], EmbedInputType.SEARCH_QUERY)
        return vectors[0]
