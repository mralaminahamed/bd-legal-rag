"""Tests for mandatory Cohere reranker (FR-QR-5, NFR-RL-2)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import Settings


def _chunk(
    cid: uuid.UUID | None = None,
    score: float = 0.5,
) -> object:
    from app.rag.retriever import RetrievedChunk

    return RetrievedChunk(
        chunk_id=cid or uuid.uuid4(),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=uuid.uuid4(),
        hierarchy_path="Act > Section 1",
        content="provision text here",
        language="en",
        score=score,
        rerank_score=None,
    )


def test_reranker_unavailable_is_exception() -> None:
    from app.rag.reranker import RerankerUnavailable

    assert issubclass(RerankerUnavailable, Exception)


@pytest.mark.asyncio
async def test_rerank_returns_chunks_with_scores() -> None:
    from app.rag.reranker import rerank

    chunks = [_chunk() for _ in range(3)]

    mock_r0 = MagicMock()
    mock_r0.index = 0
    mock_r0.relevance_score = 0.95
    mock_r1 = MagicMock()
    mock_r1.index = 1
    mock_r1.relevance_score = 0.70
    mock_r2 = MagicMock()
    mock_r2.index = 2
    mock_r2.relevance_score = 0.30

    mock_response = MagicMock()
    mock_response.results = [mock_r0, mock_r1, mock_r2]

    mock_client = AsyncMock()
    mock_client.rerank = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.rag.reranker.cohere.AsyncClient", return_value=mock_client):
        s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
        result = await rerank("weekly holiday", chunks, s)  # type: ignore[arg-type]

    assert len(result) == 3
    assert all(c.rerank_score is not None for c in result)
    scores = [c.rerank_score for c in result]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_rerank_empty_chunks_returns_empty() -> None:
    from app.rag.reranker import rerank

    s = Settings()
    result = await rerank("query", [], s)
    assert result == []


@pytest.mark.asyncio
async def test_rerank_raises_unavailable_when_no_api_key() -> None:
    from app.rag.reranker import RerankerUnavailable, rerank

    chunks = [_chunk()]
    s = Settings()  # cohere_api_key=None by default
    with pytest.raises(RerankerUnavailable):
        await rerank("query", chunks, s)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rerank_raises_unavailable_after_retries() -> None:
    """Three consecutive Cohere failures → RerankerUnavailable (NFR-RL-2)."""
    from app.rag.reranker import RerankerUnavailable, rerank

    chunks = [_chunk()]

    async def always_fail(**kwargs: object) -> None:
        raise RuntimeError("network unreachable")

    mock_client = AsyncMock()
    mock_client.rerank = AsyncMock(side_effect=always_fail)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.rag.reranker.cohere.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
            with pytest.raises(RerankerUnavailable):
                await rerank("query", chunks, s)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rerank_uses_configured_model() -> None:
    from app.rag.reranker import rerank

    chunks = [_chunk()]

    mock_result = MagicMock()
    mock_result.index = 0
    mock_result.relevance_score = 0.80

    mock_response = MagicMock()
    mock_response.results = [mock_result]

    mock_client = AsyncMock()
    mock_client.rerank = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.rag.reranker.cohere.AsyncClient", return_value=mock_client):
        s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
        await rerank("query", chunks, s)  # type: ignore[arg-type]

    call_kwargs = mock_client.rerank.call_args.kwargs
    assert call_kwargs["model"] == s.rerank_model
