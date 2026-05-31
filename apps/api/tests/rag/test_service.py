"""Tests for the retrieval service entry point (FR-QR-1..7)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from app.config import Settings


def _chunk(
    cid: uuid.UUID | None = None,
    rerank_score: float | None = None,
    act_id: uuid.UUID | None = None,
    score: float = 0.5,
) -> Any:
    from app.rag.retriever import RetrievedChunk

    return RetrievedChunk(
        chunk_id=cid or uuid.uuid4(),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=act_id or uuid.uuid4(),
        hierarchy_path="Act > Section 1",
        content="content",
        language="en",
        score=score,
        rerank_score=rerank_score,
    )


# ---------------------------------------------------------------------------
# _tier — pure function
# ---------------------------------------------------------------------------


def test_tier_low_when_not_reranked() -> None:
    from app.rag.service import _tier

    s = Settings()
    result = _tier([_chunk(rerank_score=0.99)], reranked=False, cross_lingual=False, settings=s)
    assert result == "LOW"


def test_tier_low_when_cross_lingual() -> None:
    from app.rag.service import _tier

    s = Settings()
    result = _tier([_chunk(rerank_score=0.99)], reranked=True, cross_lingual=True, settings=s)
    assert result == "LOW"


def test_tier_low_when_top_score_below_t_medium() -> None:
    from app.rag.service import _tier

    s = Settings(confidence_t_medium=0.60)
    result = _tier([_chunk(rerank_score=0.50)], reranked=True, cross_lingual=False, settings=s)
    assert result == "LOW"


def test_tier_high_when_conditions_met() -> None:
    from app.rag.service import _tier

    act = uuid.uuid4()
    s = Settings(confidence_t_high=0.85, confidence_t_medium=0.60, confidence_t_keep=0.40)
    chunks = [
        _chunk(rerank_score=0.92, act_id=act),
        _chunk(rerank_score=0.88, act_id=act),
        _chunk(rerank_score=0.45, act_id=act),
    ]
    assert _tier(chunks, reranked=True, cross_lingual=False, settings=s) == "HIGH"


def test_tier_medium_when_top_score_between_thresholds() -> None:
    from app.rag.service import _tier

    s = Settings(confidence_t_high=0.85, confidence_t_medium=0.60)
    result = _tier([_chunk(rerank_score=0.72)], reranked=True, cross_lingual=False, settings=s)
    assert result == "MEDIUM"


def test_tier_low_when_no_chunks() -> None:
    from app.rag.service import _tier

    s = Settings()
    assert _tier([], reranked=True, cross_lingual=False, settings=s) == "LOW"


# ---------------------------------------------------------------------------
# retrieve() — mocked pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_detects_bengali_language() -> None:
    from app.rag.service import retrieve

    session = AsyncMock()
    bn_query = "শ্রমিকের সাপ্তাহিক ছুটি কত দিন?"

    with patch("app.rag.service.CohereEmbedder") as mock_emb_cls:
        mock_emb = AsyncMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1] * 1024)
        mock_emb_cls.return_value = mock_emb

        with patch("app.rag.service.hybrid_retrieve", new_callable=AsyncMock) as mock_hr:
            mock_hr.return_value = []
            with patch("app.rag.service.rerank", new_callable=AsyncMock) as mock_rr:
                mock_rr.return_value = []
                s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
                result = await retrieve(session, bn_query, s, language="auto")

    assert result.detected_language == "bn"
    # First call uses "bn"
    assert mock_hr.call_args_list[0][0][4] == "bn"


@pytest.mark.asyncio
async def test_retrieve_reranker_unavailable_degrades_to_low() -> None:
    """RerankerUnavailable → LOW confidence, result still returned (NFR-RL-2)."""
    from app.rag.reranker import RerankerUnavailable
    from app.rag.service import retrieve

    session = AsyncMock()
    chunks = [_chunk(score=0.9)]

    with patch("app.rag.service.CohereEmbedder") as mock_emb_cls:
        mock_emb = AsyncMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1] * 1024)
        mock_emb_cls.return_value = mock_emb

        with patch("app.rag.service.hybrid_retrieve", new_callable=AsyncMock) as mock_hr:
            mock_hr.return_value = chunks
            with patch("app.rag.service.rerank", new_callable=AsyncMock) as mock_rr:
                mock_rr.side_effect = RerankerUnavailable("down")
                s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
                result = await retrieve(session, "weekly holiday", s)

    assert result.confidence == "LOW"
    assert result.reranked is False
    assert len(result.chunks) > 0


@pytest.mark.asyncio
async def test_retrieve_uses_today_when_as_of_date_not_supplied() -> None:
    from app.rag.service import retrieve

    session = AsyncMock()

    with patch("app.rag.service.CohereEmbedder") as mock_emb_cls:
        mock_emb = AsyncMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1] * 1024)
        mock_emb_cls.return_value = mock_emb

        with patch("app.rag.service.hybrid_retrieve", new_callable=AsyncMock) as mock_hr:
            mock_hr.return_value = []
            with patch("app.rag.service.rerank", new_callable=AsyncMock) as mock_rr:
                mock_rr.return_value = []
                s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
                result = await retrieve(session, "query", s)

    assert result.as_of_date == date.today()


@pytest.mark.asyncio
async def test_retrieve_cross_lingual_fallback_engaged() -> None:
    """When RRF top score < cross_lingual_floor, opposite-language search runs."""
    from app.rag.retriever import RetrievedChunk
    from app.rag.service import retrieve

    session = AsyncMock()
    low_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=uuid.uuid4(),
        hierarchy_path="Act > Section 1",
        content="content",
        language="en",
        score=0.05,  # below default cross_lingual_floor=0.20
        rerank_score=None,
    )

    call_count = 0

    async def fake_hr(*args: object, **kwargs: object) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [low_chunk] if call_count == 1 else []

    with patch("app.rag.service.CohereEmbedder") as mock_emb_cls:
        mock_emb = AsyncMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1] * 1024)
        mock_emb_cls.return_value = mock_emb

        with patch("app.rag.service.hybrid_retrieve", new_callable=AsyncMock) as mock_hr:
            mock_hr.side_effect = fake_hr
            with patch("app.rag.service.rerank", new_callable=AsyncMock) as mock_rr:
                mock_rr.return_value = []
                s = Settings(cohere_api_key="test-key", cross_lingual_floor=0.20)  # type: ignore[call-arg]
                result = await retrieve(session, "weekly holiday", s, language="en")

    assert mock_hr.call_count == 2
    assert result.cross_lingual is True


@pytest.mark.asyncio
async def test_retrieve_result_structure() -> None:
    from app.rag.service import RetrievalResult, retrieve

    session = AsyncMock()

    with patch("app.rag.service.CohereEmbedder") as mock_emb_cls:
        mock_emb = AsyncMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1] * 1024)
        mock_emb_cls.return_value = mock_emb

        with patch("app.rag.service.hybrid_retrieve", new_callable=AsyncMock) as mock_hr:
            mock_hr.return_value = []
            with patch("app.rag.service.rerank", new_callable=AsyncMock) as mock_rr:
                mock_rr.return_value = []
                s = Settings(cohere_api_key="test-key")  # type: ignore[call-arg]
                result = await retrieve(session, "test query", s, as_of_date=date(2024, 6, 1))

    assert isinstance(result, RetrievalResult)
    assert result.query == "test query"
    assert result.as_of_date == date(2024, 6, 1)
    assert isinstance(result.chunks, list)
    assert result.confidence in ("HIGH", "MEDIUM", "LOW")
