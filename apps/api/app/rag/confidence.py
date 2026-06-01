"""Confidence tier computation (architecture §2.5).

Computes ``HIGH | MEDIUM | LOW`` from rerank scores, cross-lingual fallback
flag, and reranker availability.  The tier is stored in ``RetrievalResult``
and influences the generator's fallback and disclaimer decisions.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from typing import Literal

from app.config import Settings
from app.rag.retriever import RetrievedChunk


def compute_confidence(
    chunks: list[RetrievedChunk],
    *,
    reranked: bool,
    cross_lingual: bool,
    settings: Settings,
) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """Compute a confidence tier from rerank results.

    Rules (in priority order):
    1. No chunks → ``LOW``.
    2. Not reranked (reranker unavailable) → ``LOW`` (NFR-RL-2).
    3. Cross-lingual fallback was used → ``LOW``.
    4. Top rerank score >= ``confidence_t_high`` → ``HIGH``.
    5. Top rerank score >= ``confidence_t_medium`` → ``MEDIUM``.
    6. Otherwise → ``LOW``.

    Args:
        chunks: Reranked chunks ordered by relevance (best first).
        reranked: ``True`` if Cohere rerank completed successfully.
        cross_lingual: ``True`` if cross-lingual fallback was used.
        settings: Application settings (threshold tunables).

    Returns:
        Literal["HIGH", "MEDIUM", "LOW"]: The computed confidence tier.
    """
    if not chunks or not reranked or cross_lingual:
        return "LOW"

    top_score = chunks[0].rerank_score or 0.0
    if top_score >= settings.confidence_t_high:
        return "HIGH"
    if top_score >= settings.confidence_t_medium:
        return "MEDIUM"
    return "LOW"
