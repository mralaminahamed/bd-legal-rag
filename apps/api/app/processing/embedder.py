"""Embedder implementations: Cohere multilingual and Ollama local.

CohereEmbedder enforces the input_type discriminator (search_document vs
search_query) at the type level — mixing them silently halves retrieval
quality (ADR-002). Use embed_documents at ingest time and embed_query at
request time.

OllamaEmbedder uses the Ollama /api/embed endpoint and supports the same
interface without an input_type discriminator (not applicable to local models).
Default model: qwen3-embedding:4b (2560 dims, multilingual, handles Bengali).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Protocol

import cohere
import httpx

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


class Embedder(Protocol):
    """Shared protocol for Cohere and Ollama embedders.

    Both implementations expose embed_documents (ingest time) and embed_query
    (request time) so call sites are provider-agnostic.
    """

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document texts (ingest time).

        Args:
            texts: Document texts to embed.

        Returns:
            list[list[float]]: One embedding vector per input text.
        """
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (request time).

        Args:
            text: Query text.

        Returns:
            list[float]: Embedding vector.
        """
        ...


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
            list[list[float]]: One embedding vector per document.
        """
        return await self.embed(texts, EmbedInputType.SEARCH_DOCUMENT)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (request time, search_query).

        Args:
            text: The query text.

        Returns:
            list[float]: An embedding vector.
        """
        vectors = await self.embed([text], EmbedInputType.SEARCH_QUERY)
        return vectors[0]


class OllamaEmbedder:
    """Local Ollama embedder using the /api/embed batch endpoint.

    Supports the same interface as CohereEmbedder so call sites are
    provider-agnostic. No input_type discriminator — local models do not
    distinguish document vs query embeddings.

    Default model: ``qwen3-embedding:4b`` (2560 dims, multilingual, handles
    Bengali and English without any Cohere dependency).

    Attributes:
        _base_url: Ollama server base URL.
        _model: Ollama embedding model name.
        _timeout: Per-request HTTP timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        batch_size: int = 32,
    ) -> None:
        """Initialise the Ollama embedder.

        Args:
            base_url: Ollama server base URL (e.g. "http://localhost:11434").
            model: Ollama model name (e.g. "qwen3-embedding:4b").
            timeout: Per-batch HTTP timeout in seconds.
            batch_size: Maximum texts per /api/embed call. Large Acts (e.g.
                Code of Criminal Procedure, 679 provisions) must be split into
                batches so each request completes within ``timeout``.
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._batch_size = batch_size

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts via Ollama /api/embed.

        Args:
            texts: Document texts to embed.

        Returns:
            list[list[float]]: One embedding vector per input text.

        Raises:
            httpx.HTTPError: On network or server failure.
        """
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string via Ollama /api/embed.

        Args:
            text: Query text.

        Returns:
            list[float]: Embedding vector.

        Raises:
            httpx.HTTPError: On network or server failure.
        """
        vectors = await self._embed([text])
        return vectors[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama /api/embed via a thread executor, batching to avoid timeouts.

        Large Acts (e.g. CrPC with 679 provisions) sent as a single request
        exceed the per-request timeout. This method splits ``texts`` into
        ``_batch_size`` chunks and processes them sequentially so each HTTP
        call completes within ``_timeout``.

        Uses a synchronous httpx.Client via run_in_executor to avoid
        event-loop inheritance issues in Celery's prefork worker pool.

        Args:
            texts: Texts to embed.

        Returns:
            list[list[float]]: One embedding vector per input text.
        """
        loop = asyncio.get_event_loop()
        results: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            batch_vectors = await loop.run_in_executor(None, self._embed_batch_sync, batch)
            results.extend(batch_vectors)
        return results

    def _embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous HTTP call for one batch of texts.

        Args:
            texts: Batch of texts (≤ _batch_size).

        Returns:
            list[list[float]]: One embedding vector per text in the batch.

        Raises:
            httpx.HTTPError: On network or server failure.
        """
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data: dict[str, list[list[float]]] = resp.json()
            return data["embeddings"]
