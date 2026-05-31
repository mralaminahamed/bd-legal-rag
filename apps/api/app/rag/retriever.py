"""Hybrid retrieval — vector + lexical + RRF fusion (FR-QR-3/4, ADR-006/007).

Exposes composable sub-functions so each stage is independently testable.
The effective-date predicate is ALWAYS applied in both search functions;
omitting it is a correctness bug (ADR-006).

Bengali lexical tokenisation uses the ``simple`` PostgreSQL text-search
configuration — Postgres ships no Bengali dictionary, and switching to
``english`` breaks Bengali recall (ADR-007).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings


@dataclass(frozen=True)
class _Hit:
    """Internal search hit before RRF fusion.

    Attributes:
        chunk_id: Chunk primary key.
        revision_id: Owning provision revision.
        provision_id: Owning provision.
        act_id: Owning Act (denormalised).
        hierarchy_path: Statutory breadcrumb string.
        content: Chunk text.
        language: ``bn`` or ``en``.
        score: Raw relevance score (cosine similarity or ts_rank_cd).
    """

    chunk_id: uuid.UUID
    revision_id: uuid.UUID
    provision_id: uuid.UUID
    act_id: uuid.UUID
    hierarchy_path: str
    content: str
    language: str
    score: float


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned by the retrieval pipeline, optionally reranked.

    Attributes:
        chunk_id: Chunk primary key.
        revision_id: Owning provision revision.
        provision_id: Owning provision.
        act_id: Owning Act (denormalised).
        hierarchy_path: Statutory breadcrumb string.
        content: Chunk text.
        language: ``bn`` or ``en``.
        score: RRF-fused retrieval score.
        rerank_score: Cohere rerank relevance score; ``None`` before reranking.
    """

    chunk_id: uuid.UUID
    revision_id: uuid.UUID
    provision_id: uuid.UUID
    act_id: uuid.UUID
    hierarchy_path: str
    content: str
    language: str
    score: float
    rerank_score: float | None


def _emb_str(embedding: list[float]) -> str:
    """Format an embedding list as pgvector's ``'[x,y,z,…]'`` literal.

    Args:
        embedding: 1024-dimensional float vector.

    Returns:
        str: pgvector-compatible string representation.
    """
    return "[" + ",".join(str(v) for v in embedding) + "]"


def _fuse(
    vector_hits: list[_Hit],
    lexical_hits: list[_Hit],
    settings: Settings,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion of vector and lexical hit lists (FR-QR-4).

    RRF score = Σ weight_L / (k + rank_L) across all lists L containing the
    chunk. Lexical matches always pass the similarity threshold; vector-only
    hits must clear ``settings.similarity_threshold``.

    Args:
        vector_hits: HNSW cosine hits, ordered by score desc.
        lexical_hits: Full-text search hits, ordered by score desc.
        settings: Settings supplying ``rrf_k``, ``vector_weight``,
            ``lexical_weight``, and ``similarity_threshold``.

    Returns:
        list[RetrievedChunk]: Fused chunks ordered by RRF score, highest first.
    """
    k = settings.rrf_k
    vw = settings.vector_weight
    lw = settings.lexical_weight

    vector_raw: dict[uuid.UUID, float] = {h.chunk_id: h.score for h in vector_hits}
    lexical_ids: set[uuid.UUID] = {h.chunk_id for h in lexical_hits}

    # Canonical hit metadata — lexical metadata preferred
    all_hits: dict[uuid.UUID, _Hit] = {}
    for h in lexical_hits:
        all_hits[h.chunk_id] = h
    for h in vector_hits:
        if h.chunk_id not in all_hits:
            all_hits[h.chunk_id] = h

    # Accumulate RRF scores from both ranked lists.
    rrf: dict[uuid.UUID, float] = {}
    for rank, h in enumerate(vector_hits, start=1):
        rrf[h.chunk_id] = rrf.get(h.chunk_id, 0.0) + vw / (k + rank)
    for rank, h in enumerate(lexical_hits, start=1):
        rrf[h.chunk_id] = rrf.get(h.chunk_id, 0.0) + lw / (k + rank)

    def _passes(cid: uuid.UUID) -> bool:
        if cid in lexical_ids:
            return True  # lexical hits always pass (FR-QR-4)
        return vector_raw.get(cid, 0.0) >= settings.similarity_threshold

    fused = [
        RetrievedChunk(
            chunk_id=h.chunk_id,
            revision_id=h.revision_id,
            provision_id=h.provision_id,
            act_id=h.act_id,
            hierarchy_path=h.hierarchy_path,
            content=h.content,
            language=h.language,
            score=rrf[h.chunk_id],
            rerank_score=None,
        )
        for cid, h in all_hits.items()
        if _passes(cid)
    ]
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


async def vector_search(
    session: AsyncSession,
    embedding: list[float],
    act_ids: list[uuid.UUID],
    language: str,
    as_of_date: date,
    settings: Settings,
) -> list[_Hit]:
    """HNSW cosine search with mandatory effective-date filter (ADR-002/006).

    Sets ``hnsw.ef_search`` for the current connection before issuing the
    HNSW query (connection-scoped, not transaction-scoped, for autocommit
    safety). The effective-date predicate is always applied — omitting it
    is a correctness bug (ADR-006).

    Args:
        session: Active async database session.
        embedding: 1024-dim query embedding (``search_query`` input_type).
        act_ids: Acts to scope; empty = all acts.
        language: ``"bn"`` or ``"en"``.
        as_of_date: Effective date for filtering provision revisions.
        settings: Application settings.

    Returns:
        list[_Hit]: Up to ``retrieval_top_n`` hits, ordered cosine similarity desc.
    """
    await session.execute(
        text("SET hnsw.ef_search = :ef"),
        {"ef": settings.ef_search},
    )

    emb = _emb_str(embedding)
    act_filter = ""
    params: dict[str, object] = {
        "emb": emb,
        "lang": language,
        "aod": as_of_date,
        "n": settings.retrieval_top_n,
    }
    if act_ids:
        act_filter = "AND c.act_id = ANY(cast(:act_ids AS uuid[]))"
        params["act_ids"] = "{" + ",".join(str(a) for a in act_ids) + "}"

    sql = text(
        f"""
        SELECT
            c.id            AS chunk_id,
            c.revision_id,
            c.provision_id,
            c.act_id,
            c.hierarchy_path,
            c.content,
            c.language,
            1 - (c.embedding <=> cast(:emb AS vector(1024))) AS score
        FROM chunks c
        JOIN provision_revisions pr ON pr.id = c.revision_id
        WHERE c.language = :lang
          {act_filter}
          AND pr.effective_from <= :aod
          AND (pr.effective_to IS NULL OR pr.effective_to >= :aod)
        ORDER BY c.embedding <=> cast(:emb AS vector(1024))
        LIMIT :n
        """
    )

    rows = (await session.execute(sql, params)).mappings().all()
    return [
        _Hit(
            chunk_id=uuid.UUID(str(row["chunk_id"])),
            revision_id=uuid.UUID(str(row["revision_id"])),
            provision_id=uuid.UUID(str(row["provision_id"])),
            act_id=uuid.UUID(str(row["act_id"])),
            hierarchy_path=str(row["hierarchy_path"]),
            content=str(row["content"]),
            language=str(row["language"]),
            score=float(row["score"]),
        )
        for row in rows
    ]


async def lexical_search(
    session: AsyncSession,
    query: str,
    act_ids: list[uuid.UUID],
    language: str,
    as_of_date: date,
    settings: Settings,
) -> list[_Hit]:
    """Full-text search via ``websearch_to_tsquery`` with the ``simple`` config (ADR-007).

    The ``simple`` text-search configuration is intentional — Postgres ships no
    Bengali dictionary, and switching to ``english`` breaks Bengali recall
    (ADR-007). The effective-date predicate is always applied (ADR-006).

    Args:
        session: Active async database session.
        query: Raw query string passed to ``websearch_to_tsquery('simple', …)``.
        act_ids: Acts to scope; empty = all acts.
        language: ``"bn"`` or ``"en"``.
        as_of_date: Effective date for filtering provision revisions.
        settings: Application settings.

    Returns:
        list[_Hit]: Up to ``retrieval_top_n`` hits ordered by ``ts_rank_cd`` desc.
    """
    act_filter = ""
    params: dict[str, object] = {
        "q": query,
        "lang": language,
        "aod": as_of_date,
        "n": settings.retrieval_top_n,
    }
    if act_ids:
        act_filter = "AND c.act_id = ANY(cast(:act_ids AS uuid[]))"
        params["act_ids"] = "{" + ",".join(str(a) for a in act_ids) + "}"

    sql = text(
        f"""
        SELECT
            c.id            AS chunk_id,
            c.revision_id,
            c.provision_id,
            c.act_id,
            c.hierarchy_path,
            c.content,
            c.language,
            ts_rank_cd(c.content_tsv, websearch_to_tsquery('simple', :q)) AS score
        FROM chunks c
        JOIN provision_revisions pr ON pr.id = c.revision_id
        WHERE c.language = :lang
          {act_filter}
          AND c.content_tsv @@ websearch_to_tsquery('simple', :q)
          AND pr.effective_from <= :aod
          AND (pr.effective_to IS NULL OR pr.effective_to >= :aod)
        ORDER BY score DESC
        LIMIT :n
        """
    )

    rows = (await session.execute(sql, params)).mappings().all()
    return [
        _Hit(
            chunk_id=uuid.UUID(str(row["chunk_id"])),
            revision_id=uuid.UUID(str(row["revision_id"])),
            provision_id=uuid.UUID(str(row["provision_id"])),
            act_id=uuid.UUID(str(row["act_id"])),
            hierarchy_path=str(row["hierarchy_path"]),
            content=str(row["content"]),
            language=str(row["language"]),
            score=float(row["score"]),
        )
        for row in rows
    ]


async def hybrid_retrieve(
    session: AsyncSession,
    query: str,
    embedding: list[float],
    act_ids: list[uuid.UUID],
    language: str,
    as_of_date: date,
    settings: Settings,
) -> list[RetrievedChunk]:
    """Orchestrate vector + lexical search and RRF fusion (FR-QR-4).

    Skips a signal entirely when its weight is zero. Runs the active
    signal(s) sequentially (shared session) and fuses via :func:`_fuse`.

    Args:
        session: Active async database session.
        query: Raw query string (lexical search).
        embedding: 1024-dim query embedding (vector search).
        act_ids: Acts to scope; empty = all acts.
        language: ``"bn"`` or ``"en"``.
        as_of_date: Effective date for filtering.
        settings: Application settings.

    Returns:
        list[RetrievedChunk]: Fused chunks ordered by RRF score, highest first.
    """
    v_hits: list[_Hit] = []
    l_hits: list[_Hit] = []

    if settings.vector_weight > 0.0:
        v_hits = await vector_search(session, embedding, act_ids, language, as_of_date, settings)
    if settings.lexical_weight > 0.0:
        l_hits = await lexical_search(session, query, act_ids, language, as_of_date, settings)

    return _fuse(v_hits, l_hits, settings)
