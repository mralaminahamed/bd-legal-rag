"""Tests for confidence tier function."""

from __future__ import annotations

import uuid

from app.config import Settings
from app.rag.retriever import RetrievedChunk


def _settings() -> Settings:
    return Settings.model_validate({})


def _chunk(rerank_score: float, language: str = "en", act_id: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=uuid.UUID(act_id) if act_id else uuid.uuid4(),
        hierarchy_path="Act > Section 1",
        content="text",
        language=language,
        score=rerank_score,
        rerank_score=rerank_score,
    )


def test_high_confidence_when_top_score_above_threshold() -> None:
    from app.rag.confidence import compute_confidence

    chunks = [_chunk(0.90), _chunk(0.85), _chunk(0.80)]
    tier = compute_confidence(chunks, reranked=True, cross_lingual=False, settings=_settings())
    assert tier == "HIGH"


def test_medium_confidence_when_top_score_between_thresholds() -> None:
    from app.rag.confidence import compute_confidence

    chunks = [_chunk(0.75), _chunk(0.65), _chunk(0.60)]
    tier = compute_confidence(chunks, reranked=True, cross_lingual=False, settings=_settings())
    assert tier == "MEDIUM"


def test_low_confidence_when_top_score_below_medium_threshold() -> None:
    from app.rag.confidence import compute_confidence

    chunks = [_chunk(0.45), _chunk(0.42)]
    tier = compute_confidence(chunks, reranked=True, cross_lingual=False, settings=_settings())
    assert tier == "LOW"


def test_low_confidence_when_cross_lingual() -> None:
    from app.rag.confidence import compute_confidence

    # High score but cross-lingual → always LOW
    chunks = [_chunk(0.95)]
    tier = compute_confidence(chunks, reranked=True, cross_lingual=True, settings=_settings())
    assert tier == "LOW"


def test_low_confidence_when_not_reranked() -> None:
    from app.rag.confidence import compute_confidence

    chunks = [_chunk(0.90)]
    tier = compute_confidence(chunks, reranked=False, cross_lingual=False, settings=_settings())
    assert tier == "LOW"


def test_low_confidence_when_no_chunks() -> None:
    from app.rag.confidence import compute_confidence

    tier = compute_confidence([], reranked=True, cross_lingual=False, settings=_settings())
    assert tier == "LOW"
