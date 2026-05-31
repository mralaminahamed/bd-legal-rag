"""Unit tests for CohereEmbedder with input_type discipline (ADR-002, FR-PR-3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_embed_input_type_values() -> None:
    from app.processing.embedder import EmbedInputType

    assert EmbedInputType.SEARCH_DOCUMENT == "search_document"
    assert EmbedInputType.SEARCH_QUERY == "search_query"
    assert EmbedInputType.SEARCH_DOCUMENT != EmbedInputType.SEARCH_QUERY


def _mock_cohere_client(n_texts: int) -> tuple[MagicMock, MagicMock]:
    """Return (mock_cls, mock_instance) that returns n_texts 1024-dim vectors."""
    mock_response = MagicMock()
    mock_response.embeddings.float_ = [[float(i % 10) / 10.0] * 1024 for i in range(n_texts)]
    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls, mock_client


@pytest.mark.asyncio
async def test_embed_documents_returns_one_vector_per_text() -> None:
    from app.processing.embedder import CohereEmbedder, EmbedInputType

    texts = ["hello", "world", "third"]
    mock_cls, _ = _mock_cohere_client(len(texts))
    with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
        embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96)
        result = await embedder.embed(texts, EmbedInputType.SEARCH_DOCUMENT)
    assert len(result) == 3
    assert all(len(v) == 1024 for v in result)


@pytest.mark.asyncio
async def test_embed_query_returns_single_vector() -> None:
    from app.processing.embedder import CohereEmbedder

    mock_cls, _ = _mock_cohere_client(1)
    with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
        embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96)
        vec = await embedder.embed_query("what is section 103?")
    assert len(vec) == 1024


@pytest.mark.asyncio
async def test_embed_documents_uses_search_document_input_type() -> None:
    from app.processing.embedder import CohereEmbedder

    mock_cls, mock_client = _mock_cohere_client(2)
    with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
        embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96)
        await embedder.embed_documents(["doc1", "doc2"])
    call_kwargs = mock_client.embed.call_args.kwargs
    assert call_kwargs["input_type"] == "search_document"


@pytest.mark.asyncio
async def test_embed_query_uses_search_query_input_type() -> None:
    from app.processing.embedder import CohereEmbedder

    mock_cls, mock_client = _mock_cohere_client(1)
    with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
        embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96)
        await embedder.embed_query("query text")
    call_kwargs = mock_client.embed.call_args.kwargs
    assert call_kwargs["input_type"] == "search_query"


@pytest.mark.asyncio
async def test_embed_empty_texts_raises_value_error() -> None:
    from app.processing.embedder import CohereEmbedder, EmbedInputType

    embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96)
    with pytest.raises(ValueError, match="texts must be non-empty"):
        await embedder.embed([], EmbedInputType.SEARCH_DOCUMENT)


@pytest.mark.asyncio
async def test_embed_batches_texts_at_batch_size() -> None:
    """200 texts with batch_size=96 should produce ceil(200/96)=3 Cohere calls."""
    import math

    from app.processing.embedder import CohereEmbedder, EmbedInputType

    n = 200
    batch_size = 96
    texts = [f"text_{i}" for i in range(n)]
    calls: list[int] = []

    async def fake_embed(**kwargs: object) -> MagicMock:
        n_batch = len(kwargs["texts"])  # type: ignore[arg-type]
        calls.append(n_batch)
        r = MagicMock()
        r.embeddings.float_ = [[0.0] * 1024 for _ in range(n_batch)]
        return r

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=fake_embed)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.processing.embedder.cohere.AsyncClient", return_value=mock_client):
        embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", batch_size)
        result = await embedder.embed(texts, EmbedInputType.SEARCH_DOCUMENT)
    assert len(calls) == math.ceil(n / batch_size)
    assert sum(calls) == n
    assert len(result) == n


@pytest.mark.asyncio
async def test_embed_retries_on_exception_and_succeeds() -> None:
    from app.processing.embedder import CohereEmbedder, EmbedInputType

    attempt_count = 0

    async def flaky_embed(**kwargs: object) -> MagicMock:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise RuntimeError("transient error")
        r = MagicMock()
        r.embeddings.float_ = [[0.0] * 1024]
        return r

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=flaky_embed)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.processing.embedder.cohere.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96, max_retries=3)
            result = await embedder.embed(["text"], EmbedInputType.SEARCH_DOCUMENT)
    assert len(result) == 1
    assert attempt_count == 2


@pytest.mark.asyncio
async def test_embed_raises_after_max_retries_exhausted() -> None:
    from app.processing.embedder import CohereEmbedder, EmbedInputType

    async def always_fail(**kwargs: object) -> None:
        raise RuntimeError("permanent error")

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=always_fail)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.processing.embedder.cohere.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            embedder = CohereEmbedder("test-key", "embed-multilingual-v3.0", 96, max_retries=2)
            with pytest.raises(RuntimeError, match="permanent error"):
                await embedder.embed(["text"], EmbedInputType.SEARCH_DOCUMENT)
