"""Retrieval pipeline entry point (FR-QR-1..7, architecture §2.4).

``retrieve()`` is the single entry point consumed by the eval harness, API
endpoints, and the generation path. It ties language detection, query
embedding, hybrid retrieval, cross-lingual fallback, mandatory reranking, and
confidence tiering into one call.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.processing.embedder import CohereEmbedder, OllamaEmbedder
from app.rag.confidence import compute_confidence
from app.rag.lang_router import detect_language
from app.rag.reranker import RerankerUnavailable, rerank
from app.rag.retriever import RetrievedChunk, hybrid_retrieve

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """The outcome of one retrieval pipeline run.

    Attributes:
        query: Original query string.
        detected_language: Language detected from the query.
        act_ids: Acts that were searched (empty = all acts).
        cross_lingual: ``True`` when the cross-lingual fallback was attempted (top
        RRF score fell below ``cross_lingual_floor``), regardless of whether it
        found additional results. A True value always yields ``LOW`` confidence.
        chunks: Retrieved and reranked chunks, ordered by relevance.
        reranked: ``True`` when Cohere rerank completed successfully.
        confidence: Confidence tier based on rerank scores.
        as_of_date: Effective date used for chunk filtering.
    """

    query: str
    detected_language: Literal["bn", "en", "mixed"]
    act_ids: list[uuid.UUID]
    cross_lingual: bool
    chunks: list[RetrievedChunk]
    reranked: bool
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    as_of_date: date


def _tier(
    chunks: list[RetrievedChunk],
    reranked: bool,
    cross_lingual: bool,
    settings: Settings,
) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """Delegate to :func:`app.rag.confidence.compute_confidence`.

    Args:
        chunks: Reranked (or unreranked) chunks.
        reranked: Whether Cohere rerank succeeded.
        cross_lingual: Whether cross-lingual fallback was used.
        settings: Confidence threshold settings.

    Returns:
        Literal["HIGH", "MEDIUM", "LOW"]: The confidence tier.
    """
    return compute_confidence(
        chunks, reranked=reranked, cross_lingual=cross_lingual, settings=settings
    )


async def retrieve(
    session: AsyncSession,
    query: str,
    settings: Settings | None = None,
    *,
    act_ids: list[uuid.UUID] | None = None,
    language: Literal["bn", "en", "auto"] = "auto",
    as_of_date: date | None = None,
) -> RetrievalResult:
    """Run the full retrieval pipeline for one query (FR-QR-1..7).

    Pipeline:
    1. Detect language (Unicode-block analysis when ``language="auto"``).
    2. Embed query with ``search_query`` input_type (ADR-002).
    3. Hybrid retrieve (vector + lexical + RRF fusion) in primary language.
    4. Cross-lingual fallback when RRF top score < ``cross_lingual_floor`` (FR-QR-3).
    5. Mandatory Cohere rerank (FR-QR-5); degrades to LOW on failure (NFR-RL-2).
    6. Confidence tiering.

    Args:
        session: Active async database session.
        query: Free-text search query.
        settings: Application settings; resolved via ``get_settings()`` if ``None``.
        act_ids: Acts to scope; ``None`` or empty = all acts.
        language: ``"auto"`` detects from script; ``"bn"``/``"en"`` overrides.
        as_of_date: Effective date for filtering; ``None`` = today.

    Returns:
        RetrievalResult: Full pipeline result with reranked chunks and tier.
    """
    cfg = settings or get_settings()
    scope: list[uuid.UUID] = act_ids or []
    aod = as_of_date if as_of_date is not None else date.today()

    # --- 1. Language detection ---
    if language == "auto":
        detected, _ = detect_language(query)
    else:
        detected = language
    search_lang = "bn" if detected == "bn" else "en"

    # --- 2. Embed query ---
    # When Cohere key is absent or empty, degrade to lexical-only retrieval.
    # Embedding is optional; hybrid_retrieve skips vector search when None.
    _cohere_key = (
        cfg.cohere_api_key.get_secret_value() if cfg.cohere_api_key else ""
    )
    embedding: list[float] | None = None
    if _cohere_key:
        embedder: CohereEmbedder | OllamaEmbedder = CohereEmbedder(
            api_key=_cohere_key,
            model=cfg.embed_model,
            batch_size=cfg.embed_batch_size,
        )
        embedding = await embedder.embed_query(query)
    else:
        logger.info(
            "BDRAG_COHERE_API_KEY not configured — using Ollama embedder (%s)",
            cfg.ollama_embed_model,
        )
        embedder = OllamaEmbedder(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_embed_model,
        )
        embedding = await embedder.embed_query(query)

    # --- 3. Primary hybrid retrieve ---
    candidates = await hybrid_retrieve(session, query, embedding, scope, search_lang, aod, cfg)

    # --- 4. Cross-lingual fallback (FR-QR-3) ---
    cross_lingual = False
    top_score = candidates[0].score if candidates else 0.0
    if top_score < cfg.cross_lingual_floor:
        cross_lingual = True
        other_lang = "en" if search_lang == "bn" else "bn"
        other = await hybrid_retrieve(session, query, embedding, scope, other_lang, aod, cfg)
        if other:
            merged = candidates + other
            merged.sort(key=lambda c: c.score, reverse=True)
            candidates = merged

    # --- 5. Mandatory rerank (FR-QR-5, NFR-RL-2) ---
    reranked = False
    try:
        candidates = await rerank(query, candidates[: cfg.rerank_top_n], cfg)
        reranked = True
    except RerankerUnavailable:
        pass  # degrade to LOW; still return unreranked top-k

    final = candidates[: cfg.retrieval_top_k]

    # --- 6. Confidence tiering ---
    confidence = _tier(final, reranked, cross_lingual, cfg)

    return RetrievalResult(
        query=query,
        detected_language=detected,
        act_ids=scope,
        cross_lingual=cross_lingual,
        chunks=final,
        reranked=reranked,
        confidence=confidence,
        as_of_date=aod,
    )
