"""Public query and feedback endpoints (FR-DL-1..3, FR-FB-1..2).

POST /api/v1/query          — grounded answer with citations and disclaimer.
POST /api/v1/query/stream   — SSE token stream then final event.
POST /api/v1/feedback       — store user rating bound to a prior query.

Rate limiting is applied per-hashed-IP via Redis (NFR-SC-2).
Every response path injects the disclaimer (NFR-LS-1).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, rate_limit
from app.api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    QueryRequest,
    QueryResponse,
    ThreadListResponse,
    ThreadMessage,
    ThreadResponse,
    ThreadSummary,
)
from app.config import Settings, get_settings
from app.db.models import Act, Feedback, Query
from app.rag.generator import GenerateResponse, StreamEvent, generate, generate_stream
from app.rag.service import retrieve

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


def _ip_hash(request: Request) -> str:
    """Return a 16-hex-char SHA-256 digest of the caller IP (NFR-SC-2).

    Args:
        request: Incoming HTTP request.

    Returns:
        str: Truncated hex digest of the caller IP.
    """
    raw = (request.client.host if request.client else "unknown").encode()
    return hashlib.sha256(raw).hexdigest()[:16]


async def _resolve_act_id(
    session: AsyncSession, slug: str | None
) -> uuid.UUID | None:
    """Return the Act UUID for *slug*, or raise 404 when unknown.

    Args:
        session: Async database session.
        slug: Act slug or None.

    Returns:
        uuid.UUID | None: Act UUID or None if slug is None.

    Raises:
        HTTPException: 404 when the slug is not found.
    """
    if slug is None:
        return None
    result = await session.execute(select(Act).where(Act.slug == slug))
    act = result.scalar_one_or_none()
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"act not found: {slug!r}",
        )
    return act.id


async def _log_query(
    session: AsyncSession,
    *,
    request: Request,
    body: QueryRequest,
    gen: GenerateResponse,
    detected_language: str,
    act_id: uuid.UUID | None,
    chunk_ids: list[uuid.UUID],
    rerank_top_score: float | None,
    confidence: str,
    latency_ms: int,
) -> Query:
    """Persist a Query record and return it (FR-FB-1).

    Args:
        session: Async database session.
        request: Incoming HTTP request.
        body: Validated query request.
        gen: Generation result.
        detected_language: Language detected from query.
        act_id: Scoped Act UUID or None.
        chunk_ids: Retrieved chunk UUIDs.
        rerank_top_score: Top rerank score or None.
        confidence: Confidence tier string.
        latency_ms: End-to-end latency.

    Returns:
        Query: The persisted ORM record.
    """
    # detected_language is Literal["bn","en","mixed"]; DB check expects "bn" or "en"
    lang: Literal["bn", "en"] = "en" if detected_language != "bn" else "bn"
    selected: Literal["bn", "en"] = body.language or lang  # type: ignore[assignment]

    record = Query(
        correlation_id=request.headers.get("X-Correlation-ID", ""),
        detected_language=lang,
        selected_language=selected,
        act_ids=[act_id] if act_id else [],
        as_of_date=body.as_of_date,
        query_text=body.question,
        retrieved_chunk_ids=chunk_ids,
        rerank_top_score=rerank_top_score,
        declined=gen.declined,
        decline_reason=None,
        confidence_tier=confidence,
        degraded=gen.degraded,
        response_text=gen.answer,
        provider=None,
        prompt_version=None,
        disclaimer_version=gen.disclaimer_version,
        tokens_in=gen.usage.input_tokens if gen.usage is not None else None,
        tokens_out=gen.usage.output_tokens if gen.usage is not None else None,
        cost_usd=None,
        cached=gen.cached,
        latency_ms=latency_ms,
        ip_hash=_ip_hash(request),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(rate_limit)],
    summary="Answer a legal question (FR-DL-1)",
)
async def query_endpoint(
    request: Request,
    body: QueryRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    """Return a grounded, cited, disclaimer-bearing answer.

    Args:
        request: Incoming HTTP request (for correlation id and IP).
        body: Validated query request.
        session: Async database session.
        settings: Application settings.

    Returns:
        QueryResponse: Full generation result with metadata.
    """
    start = time.monotonic()

    act_id = await _resolve_act_id(session, body.act_slug)
    act_ids = [act_id] if act_id else []
    language = body.language or "auto"

    retrieval = await retrieve(
        session,
        body.question,
        settings,
        act_ids=act_ids,
        language=language,  # type: ignore[arg-type]
        as_of_date=body.as_of_date,
    )

    gen = await generate(
        retrieval_result=retrieval,
        session=session,
        settings=settings,
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    rerank_top = retrieval.chunks[0].rerank_score if retrieval.chunks else None
    chunk_ids = [c.chunk_id for c in retrieval.chunks]

    record = await _log_query(
        session,
        request=request,
        body=body,
        gen=gen,
        detected_language=retrieval.detected_language,
        act_id=act_id,
        chunk_ids=chunk_ids,
        rerank_top_score=rerank_top,
        confidence=retrieval.confidence,
        latency_ms=latency_ms,
    )

    return QueryResponse(
        query_id=str(record.id),
        answer=gen.answer,
        citations=gen.citations,
        disclaimer=gen.disclaimer,
        disclaimer_version=gen.disclaimer_version,
        confidence=retrieval.confidence,
        cached=gen.cached,
        degraded=gen.degraded,
        declined=gen.declined,
        detected_language=retrieval.detected_language,
        as_of_date=body.as_of_date,
    )


@router.post(
    "/query/stream",
    dependencies=[Depends(rate_limit)],
    summary="Stream a legal question answer (FR-DL-1)",
    response_class=StreamingResponse,
)
async def query_stream_endpoint(
    request: Request,
    body: QueryRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Stream token events then a final validated event over SSE.

    Args:
        request: Incoming HTTP request.
        body: Validated query request.
        session: Async database session.
        settings: Application settings.

    Returns:
        StreamingResponse: Server-sent events stream.
    """
    start = time.monotonic()

    act_id = await _resolve_act_id(session, body.act_slug)
    act_ids = [act_id] if act_id else []
    language = body.language or "auto"

    retrieval = await retrieve(
        session,
        body.question,
        settings,
        act_ids=act_ids,
        language=language,  # type: ignore[arg-type]
        as_of_date=body.as_of_date,
    )

    final_event: list[StreamEvent] = []

    async def _event_stream() -> AsyncGenerator[str, None]:
        async for event in generate_stream(
            retrieval_result=retrieval,
            session=session,
            settings=settings,
        ):
            payload = {
                "type": event.type,
                "text": event.text,
                "answer": event.answer,
                "citations": event.citations,
                "disclaimer": event.disclaimer,
                "cached": event.cached,
                "degraded": event.degraded,
                "declined": event.declined,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            if event.type == "final":
                final_event.append(event)

        if final_event:
            ev = final_event[0]
            gen = GenerateResponse(
                answer=ev.answer or "",
                citations=ev.citations or [],
                disclaimer=ev.disclaimer or "",
                cached=ev.cached,
                degraded=ev.degraded,
                declined=ev.declined,
                usage=ev.usage,
                disclaimer_version=settings.active_disclaimer_version,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            chunk_ids = [c.chunk_id for c in retrieval.chunks]
            rerank_top = retrieval.chunks[0].rerank_score if retrieval.chunks else None
            await _log_query(
                session,
                request=request,
                body=body,
                gen=gen,
                detected_language=retrieval.detected_language,
                act_id=act_id,
                chunk_ids=chunk_ids,
                rerank_top_score=rerank_top,
                confidence=retrieval.confidence,
                latency_ms=latency_ms,
            )
        else:
            logger.warning("stream completed with no final event")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit)],
    summary="Submit user feedback (FR-FB-2)",
)
async def feedback_endpoint(
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Accept user feedback bound to a prior query.

    Args:
        body: Validated feedback request.
        session: Async database session.

    Returns:
        FeedbackResponse: Confirmation with the created feedback id.

    Raises:
        HTTPException: 404 when the query_id does not exist.
        HTTPException: 422 when query_id is not a valid UUID.
    """
    try:
        qid = uuid.UUID(body.query_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query_id must be a valid UUID",
        ) from exc

    exists = await session.get(Query, qid)
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"query not found: {body.query_id!r}",
        )

    record = Feedback(
        query_id=qid,
        rating=body.rating,
        comment=body.comment,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return FeedbackResponse(
        feedback_id=str(record.id),
        query_id=body.query_id,
        rating=body.rating,
    )


@router.get(
    "/thread/{thread_id}",
    response_model=ThreadResponse,
    summary="Retrieve all messages in a playground thread",
)
async def thread_endpoint(
    thread_id: str,
    session: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Return all Query rows whose correlation_id matches thread_id, oldest first.

    The playground sends the thread UUID as the ``X-Correlation-ID`` header on
    every stream request so all messages in a conversation share a correlation_id.

    Args:
        thread_id: The playground thread UUID (correlation_id on Query rows).
        session: Async database session.

    Returns:
        ThreadResponse: Ordered list of messages for this thread.
    """
    result = await session.execute(
        select(Query)
        .where(Query.correlation_id == thread_id)
        .order_by(Query.created_at),
    )
    rows = list(result.scalars().all())

    messages = [
        ThreadMessage(
            id=str(q.id),
            question=q.query_text,
            answer=q.response_text,
            disclaimer=None,  # embedded in response_text; extracted client-side
            declined=q.declined,
            cached=q.cached,
            degraded=q.degraded,
            confidence_tier=q.confidence_tier,
            detected_language=q.detected_language,
            created_at=q.created_at,
        )
        for q in rows
    ]

    return ThreadResponse(thread_id=thread_id, messages=messages)


@router.get(
    "/threads",
    response_model=ThreadListResponse,
    summary="List all playground threads ordered by last activity",
)
async def list_threads_endpoint(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> ThreadListResponse:
    """Return all distinct playground threads with summary metadata.

    Only threads with a non-empty correlation_id (playground threads) are
    included. Results are ordered by last activity descending so the most
    recent conversations appear first.

    Args:
        limit: Maximum threads to return (default 50).
        offset: Pagination offset (default 0).
        session: Async database session.

    Returns:
        ThreadListResponse: Paginated thread summaries.
    """
    # Each thread = one distinct non-empty correlation_id
    # Aggregate: first question, count, last activity, last detected_language
    agg_sql = text(
        """
        SELECT
            correlation_id                              AS thread_id,
            (array_agg(query_text ORDER BY created_at))[1] AS first_question,
            COUNT(*)                                    AS message_count,
            MAX(created_at)                             AS last_activity,
            (array_agg(detected_language ORDER BY created_at DESC))[1] AS detected_language
        FROM queries
        WHERE correlation_id IS NOT NULL
          AND correlation_id <> ''
        GROUP BY correlation_id
        ORDER BY last_activity DESC
        LIMIT :limit OFFSET :offset
        """
    )

    count_sql = text(
        """
        SELECT COUNT(DISTINCT correlation_id)
        FROM queries
        WHERE correlation_id IS NOT NULL
          AND correlation_id <> ''
        """
    )

    rows = (await session.execute(agg_sql, {"limit": limit, "offset": offset})).mappings().all()
    total: int = (await session.execute(count_sql)).scalar_one() or 0

    threads = [
        ThreadSummary(
            thread_id=str(row["thread_id"]),
            first_question=str(row["first_question"]),
            message_count=int(row["message_count"]),
            last_activity=row["last_activity"],
            detected_language=row["detected_language"],
        )
        for row in rows
    ]

    return ThreadListResponse(threads=threads, total=total)
