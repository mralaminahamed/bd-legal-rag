"""Tests for hybrid retriever — _fuse, vector_search, lexical_search, hybrid_retrieve."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import Settings

_ACT = uuid.uuid4()
_REV = uuid.uuid4()
_PRV = uuid.uuid4()


def _hit(cid: uuid.UUID, score: float, lang: str = "en") -> Any:
    from app.rag.retriever import _Hit

    return _Hit(
        chunk_id=cid,
        revision_id=_REV,
        provision_id=_PRV,
        act_id=_ACT,
        hierarchy_path="Act > Section 1",
        content="some content",
        language=lang,
        score=score,
    )


def test_fuse_vector_only_hits_above_threshold_included() -> None:
    from app.rag.retriever import _fuse

    cid = uuid.uuid4()
    s = Settings(similarity_threshold=0.10, vector_weight=1.0, lexical_weight=0.0)
    result = _fuse([_hit(cid, score=0.90)], [], s)
    assert len(result) == 1
    assert result[0].chunk_id == cid


def test_fuse_vector_only_hits_below_threshold_excluded() -> None:
    from app.rag.retriever import _fuse

    cid = uuid.uuid4()
    s = Settings(similarity_threshold=0.50, vector_weight=1.0, lexical_weight=0.0)
    result = _fuse([_hit(cid, score=0.20)], [], s)
    assert result == []


def test_fuse_lexical_hits_always_pass_threshold() -> None:
    from app.rag.retriever import _fuse

    cid = uuid.uuid4()
    s = Settings(similarity_threshold=0.99, vector_weight=0.0, lexical_weight=1.0)
    result = _fuse([], [_hit(cid, score=0.01)], s)
    assert len(result) == 1
    assert result[0].chunk_id == cid


def test_fuse_rrf_scores_higher_rank_wins() -> None:
    from app.rag.retriever import _fuse

    c1, c2 = uuid.uuid4(), uuid.uuid4()
    s = Settings(rrf_k=60, vector_weight=1.0, lexical_weight=0.0, similarity_threshold=0.0)
    result = _fuse([_hit(c1, 0.9), _hit(c2, 0.5)], [], s)
    assert result[0].chunk_id == c1
    assert result[0].score > result[1].score


def test_fuse_both_lists_chunk_gets_combined_score() -> None:
    from app.rag.retriever import _fuse

    shared = uuid.uuid4()
    only_vec = uuid.uuid4()
    s = Settings(rrf_k=60, vector_weight=1.0, lexical_weight=1.0, similarity_threshold=0.0)
    v_hits = [_hit(shared, 0.9), _hit(only_vec, 0.8)]
    l_hits = [_hit(shared, 0.7)]
    result = _fuse(v_hits, l_hits, s)

    shared_chunk = next(c for c in result if c.chunk_id == shared)
    only_vec_chunk = next(c for c in result if c.chunk_id == only_vec)
    assert shared_chunk.score > only_vec_chunk.score


def test_fuse_empty_inputs_returns_empty() -> None:
    from app.rag.retriever import _fuse

    s = Settings()
    assert _fuse([], [], s) == []


def test_fuse_rerank_score_is_none_before_reranking() -> None:
    from app.rag.retriever import _fuse

    cid = uuid.uuid4()
    s = Settings(similarity_threshold=0.0, vector_weight=1.0, lexical_weight=0.0)
    result = _fuse([_hit(cid, 0.8)], [], s)
    assert result[0].rerank_score is None


def test_fuse_result_sorted_descending_by_score() -> None:
    from app.rag.retriever import _fuse

    ids = [uuid.uuid4() for _ in range(4)]
    s = Settings(rrf_k=60, vector_weight=1.0, lexical_weight=0.0, similarity_threshold=0.0)
    hits = [_hit(ids[i], float(4 - i) / 10) for i in range(4)]
    result = _fuse(hits, [], s)
    scores = [c.score for c in result]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_vector_search_returns_hits_from_rows() -> None:
    from app.rag.retriever import _Hit, vector_search

    cid = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {  # type: ignore[misc]
        "chunk_id": str(cid),
        "revision_id": str(_REV),
        "provision_id": str(_PRV),
        "act_id": str(_ACT),
        "hierarchy_path": "Act > Section 1",
        "content": "content",
        "language": "en",
        "score": 0.85,
    }[k]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [row]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    hits = await vector_search(session, [0.1] * 1024, [], "en", date(2024, 1, 1), Settings())

    assert len(hits) == 1
    assert isinstance(hits[0], _Hit)
    assert hits[0].chunk_id == cid
    assert hits[0].score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_vector_search_empty_result() -> None:
    from app.rag.retriever import vector_search

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    hits = await vector_search(session, [0.0] * 1024, [], "bn", date(2024, 1, 1), Settings())
    assert hits == []


@pytest.mark.asyncio
async def test_lexical_search_returns_hits_from_rows() -> None:
    from app.rag.retriever import _Hit, lexical_search

    cid = uuid.uuid4()
    row = MagicMock()
    row.__getitem__ = lambda self, k: {  # type: ignore[misc]
        "chunk_id": str(cid),
        "revision_id": str(_REV),
        "provision_id": str(_PRV),
        "act_id": str(_ACT),
        "hierarchy_path": "Act > Section 103",
        "content": "weekly holiday content",
        "language": "en",
        "score": 0.42,
    }[k]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [row]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    hits = await lexical_search(session, "weekly holiday", [], "en", date(2024, 1, 1), Settings())

    assert len(hits) == 1
    assert isinstance(hits[0], _Hit)
    assert hits[0].chunk_id == cid


@pytest.mark.asyncio
async def test_hybrid_retrieve_skips_vector_when_weight_zero() -> None:
    from app.rag.retriever import hybrid_retrieve

    session = AsyncMock()
    s = Settings(vector_weight=0.0, lexical_weight=1.0)

    with patch("app.rag.retriever.vector_search") as mock_vec:
        with patch("app.rag.retriever.lexical_search", new_callable=AsyncMock) as mock_lex:
            mock_lex.return_value = []
            await hybrid_retrieve(session, "query", [0.1] * 1024, [], "en", date.today(), s)
            mock_vec.assert_not_called()


@pytest.mark.asyncio
async def test_hybrid_retrieve_skips_lexical_when_weight_zero() -> None:
    from app.rag.retriever import hybrid_retrieve

    session = AsyncMock()
    s = Settings(lexical_weight=0.0, vector_weight=1.0)

    with patch("app.rag.retriever.vector_search", new_callable=AsyncMock) as mock_vec:
        with patch("app.rag.retriever.lexical_search") as mock_lex:
            mock_vec.return_value = []
            await hybrid_retrieve(session, "query", [0.1] * 1024, [], "en", date.today(), s)
            mock_lex.assert_not_called()


@pytest.mark.asyncio
async def test_vector_search_sql_contains_effective_date_filter() -> None:
    """The effective-date predicate must always be present in vector_search SQL (ADR-006)."""
    from app.rag.retriever import vector_search

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    await vector_search(session, [0.1] * 1024, [], "en", date(2010, 1, 1), Settings())

    # The second execute call is the SELECT (first is SET hnsw.ef_search)
    select_call = session.execute.call_args_list[1]
    sql_text = str(select_call[0][0])  # first positional arg is the text() object
    assert "effective_from" in sql_text
    assert "effective_to" in sql_text
