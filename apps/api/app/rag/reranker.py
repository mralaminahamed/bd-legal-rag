"""Cohere cross-encoder reranker — mandatory stage (FR-QR-5, ADR-003).

Reranking is a structural requirement in this system, not an optimisation:
legal queries demand precision, and the RRF fused candidate set is broad.
When the reranker is unreachable, callers catch :exc:`RerankerUnavailable`
and surface ``LOW`` confidence rather than failing the request (NFR-RL-2).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import logging

import cohere

from app.config import Settings
from app.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 30.0


class RerankerUnavailable(Exception):  # noqa: N818  # name is an architectural contract (CLAUDE.md)
    """Raised when the Cohere reranker is unreachable after all retries.

    The caller MUST catch this and degrade to ``LOW`` confidence rather than
    propagating the error to the user (NFR-RL-2).
    """


async def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    settings: Settings,
) -> list[RetrievedChunk]:
    """Rerank chunks with Cohere ``rerank-multilingual-v3.0`` (FR-QR-5).

    Returns at most ``settings.rerank_top_n`` chunks ordered by rerank score,
    highest first, with ``rerank_score`` populated on each.

    Args:
        query: The original search query.
        chunks: Fused candidate chunks from hybrid retrieval.
        settings: Application settings (rerank model, ``top_n``, API key).

    Returns:
        list[RetrievedChunk]: Reranked chunks with ``rerank_score`` set.

    Raises:
        RerankerUnavailable: When Cohere is unreachable after retries, so the
            caller can degrade to LOW confidence (NFR-RL-2).
    """
    if not chunks:
        return []
    if settings.cohere_api_key is None:
        raise RerankerUnavailable("cohere_api_key not configured")

    api_key = settings.cohere_api_key.get_secret_value()
    top_n = min(settings.rerank_top_n, len(chunks))
    documents = [c.content for c in chunks]

    last_exc: Exception | None = None
    client = cohere.AsyncClient(api_key=api_key)

    async with client:
        for attempt in range(3):
            try:
                response = await client.rerank(
                    model=settings.rerank_model,
                    query=query,
                    documents=documents,
                    top_n=top_n,
                )
                scored: list[RetrievedChunk] = []
                for result in response.results:
                    c = chunks[result.index]
                    scored.append(
                        RetrievedChunk(
                            chunk_id=c.chunk_id,
                            revision_id=c.revision_id,
                            provision_id=c.provision_id,
                            act_id=c.act_id,
                            hierarchy_path=c.hierarchy_path,
                            content=c.content,
                            language=c.language,
                            score=c.score,
                            rerank_score=result.relevance_score,
                        )
                    )
                scored.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)
                return scored
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < 2:
                    wait = min(2.0**attempt, _MAX_BACKOFF_SECONDS)
                    logger.warning(
                        "rerank attempt failed, retrying",
                        extra={"attempt": attempt, "wait_seconds": wait, "error": str(exc)},
                    )
                    await asyncio.sleep(wait)

    raise RerankerUnavailable(f"reranker unreachable: {last_exc}") from last_exc
