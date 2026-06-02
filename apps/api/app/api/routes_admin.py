"""Admin endpoints (bearer-authenticated, NFR-SC-2).

Acts with ingestion state, ingestion triggers, LLM override,
metrics (24h window), and recent queries feed.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis, require_admin
from app.api.schemas import (
    AdminActSummary,
    ConfidenceBreakdown,
    IngestionRunSummary,
    IngestionTriggerResponse,
    LLMOverrideRequest,
    LLMOverrideResponse,
    MetricsResponse,
    RecentQueriesResponse,
    RecentQuery,
)
from app.config import ProviderName, Settings, get_settings
from app.db.models import Act, IngestionRun, Query
from app.llm import runtime as llm_runtime

logger = logging.getLogger(__name__)

# Redis key helpers for tracking active ingestion task IDs.
_KEY_ALL = "ingest:active"          # SET of all active task IDs
_KEY_ACT = "ingest:act:{slug}"      # SET of task IDs for one act
_TTL = 7200                         # 2 h — tasks complete well before this

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def _run_to_summary(run: IngestionRun | None) -> IngestionRunSummary | None:
    """Convert an IngestionRun row to a summary, or None.

    Args:
        run: IngestionRun ORM instance or None.

    Returns:
        IngestionRunSummary | None: Serialisable summary or None.
    """
    if run is None:
        return None
    return IngestionRunSummary(
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        provisions_processed=run.provisions_processed,
        chunks_created=run.chunks_created,
        error=run.error,
    )


@router.get("/acts", response_model=list[AdminActSummary])
async def admin_acts(session: AsyncSession = Depends(get_db)) -> list[AdminActSummary]:
    """Return all Acts with their latest ingestion run per language.

    Args:
        session: Async database session.

    Returns:
        list[AdminActSummary]: Acts with ingestion metadata.
    """
    acts_result = await session.execute(
        select(Act).order_by(Act.act_year, Act.full_name_en)
    )
    acts = list(acts_result.scalars().all())

    summaries: list[AdminActSummary] = []
    for act in acts:
        bn_result = await session.execute(
            select(IngestionRun)
            .where(IngestionRun.act_id == act.id, IngestionRun.language == "bn")
            .order_by(IngestionRun.started_at.desc())
            .limit(1)
        )
        en_result = await session.execute(
            select(IngestionRun)
            .where(IngestionRun.act_id == act.id, IngestionRun.language == "en")
            .order_by(IngestionRun.started_at.desc())
            .limit(1)
        )
        bn_run = bn_result.scalar_one_or_none()
        en_run = en_result.scalar_one_or_none()

        summaries.append(
            AdminActSummary(
                id=str(act.id),
                slug=act.slug,
                short_name=act.short_name,
                full_name_en=act.full_name_en,
                act_year=act.act_year,
                status=act.status,
                last_run_bn=_run_to_summary(bn_run),
                last_run_en=_run_to_summary(en_run),
            )
        )

    return summaries


@router.post("/acts/ingest", response_model=IngestionTriggerResponse, status_code=202)
async def ingest_all(
    session: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),  # noqa: ARG001
) -> IngestionTriggerResponse:
    """Dispatch Celery ingestion tasks for every Act in both languages.

    One ``ingest_act_language_task`` is dispatched per ``(act, language)`` pair
    so each pair is independently tracked and does not block siblings (FR-IN-5).

    Args:
        session: Async database session.
        redis: Unused injected dependency; task IDs stored via direct client call.

    Returns:
        IngestionTriggerResponse: Dispatched Celery task IDs.
    """
    # Import at call-time to avoid circular imports and allow Celery to be optional
    # during testing when the broker is unavailable.
    from app.ingestion.tasks import ingest_act_language_task

    acts_result = await session.execute(select(Act).order_by(Act.act_year, Act.full_name_en))
    acts = list(acts_result.scalars().all())

    task_ids: list[str] = []
    act_task_map: dict[str, list[str]] = {}
    for act in acts:
        act_task_map[act.slug] = []
        for lang in ("bn", "en"):
            result = ingest_act_language_task.delay(str(act.id), lang)
            task_ids.append(result.id)
            act_task_map[act.slug].append(result.id)

    # Store task IDs in Redis for cancellation
    from app.db.redis import get_redis as _get_redis  # noqa: PLC0415
    r = _get_redis()
    if task_ids:
        await r.sadd(_KEY_ALL, *task_ids)  # type: ignore[misc]
        await r.expire(_KEY_ALL, _TTL)
    for slug, ids in act_task_map.items():
        if ids:
            key = _KEY_ACT.format(slug=slug)
            await r.sadd(key, *ids)  # type: ignore[misc]
            await r.expire(key, _TTL)

    logger.info(
        "admin triggered all-acts ingestion",
        extra={"act_count": len(acts), "task_count": len(task_ids)},
    )
    return IngestionTriggerResponse(
        task_ids=task_ids,
        message=f"Dispatched {len(task_ids)} ingestion tasks for {len(acts)} acts.",
    )


@router.post("/acts/{slug}/ingest", response_model=IngestionTriggerResponse, status_code=202)
async def ingest_act_route(
    slug: str,
    session: AsyncSession = Depends(get_db),
) -> IngestionTriggerResponse:
    """Dispatch Celery ingestion tasks for one Act in both languages.

    One ``ingest_act_language_task`` per language is dispatched independently so
    a failure in one language does not abort the other (FR-IN-5).

    Args:
        slug: Act slug.
        session: Async database session.

    Returns:
        IngestionTriggerResponse: Dispatched Celery task IDs.

    Raises:
        HTTPException: 404 when the slug is unknown.
    """
    # Import at call-time to avoid circular imports.
    from app.ingestion.tasks import ingest_act_language_task

    act_result = await session.execute(select(Act).where(Act.slug == slug))
    act = act_result.scalar_one_or_none()
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Act with slug '{slug}' not found.",
        )

    task_ids: list[str] = []
    for lang in ("bn", "en"):
        result = ingest_act_language_task.delay(str(act.id), lang)
        task_ids.append(result.id)

    # Store task IDs in Redis for cancellation
    from app.db.redis import get_redis as _get_redis  # noqa: PLC0415
    r = _get_redis()
    if task_ids:
        await r.sadd(_KEY_ALL, *task_ids)  # type: ignore[misc]
        await r.expire(_KEY_ALL, _TTL)
        key = _KEY_ACT.format(slug=slug)
        await r.sadd(key, *task_ids)  # type: ignore[misc]
        await r.expire(key, _TTL)

    logger.info(
        "admin triggered single-act ingestion",
        extra={"act_slug": slug, "act_id": str(act.id), "task_count": len(task_ids)},
    )
    return IngestionTriggerResponse(
        task_ids=task_ids,
        message=f"Dispatched {len(task_ids)} ingestion tasks for act '{slug}'.",
    )


@router.delete("/acts/ingest", status_code=200)
async def cancel_all_ingestion(
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Revoke all active ingestion tasks and mark running DB rows as failed.

    Args:
        session: Async database session.

    Returns:
        dict: Revoked count and message.
    """
    from app.db.redis import get_redis as _get_redis  # noqa: PLC0415
    from app.ingestion.tasks import celery_app  # noqa: PLC0415

    r = _get_redis()
    task_ids = list(await r.smembers(_KEY_ALL))  # type: ignore[misc]

    if task_ids:
        celery_app.control.revoke(task_ids, terminate=True, signal="SIGTERM")
        await r.delete(_KEY_ALL)
        # Also delete all per-act keys
        act_keys = await r.keys(_KEY_ACT.format(slug="*"))
        if act_keys:
            await r.delete(*act_keys)

    # Mark all running DB rows as failed
    running_rows = list(
        (
            await session.execute(
                select(IngestionRun).where(IngestionRun.status == "running")
            )
        )
        .scalars()
        .all()
    )
    for run in running_rows:
        run.status = "failed"
        run.error = "Cancelled by operator"
    if running_rows:
        await session.commit()

    revoked = len(task_ids)
    logger.info("admin cancelled all ingestion", extra={"revoked": revoked})
    return {"revoked": revoked, "message": f"Revoked {revoked} tasks."}


@router.delete("/acts/{slug}/ingest", status_code=200)
async def cancel_act_ingestion(
    slug: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Revoke active ingestion tasks for one Act and mark running rows as failed.

    Args:
        slug: Act slug.
        session: Async database session.

    Returns:
        dict: Revoked count and message.

    Raises:
        HTTPException: 404 when the slug is unknown.
    """
    from app.db.redis import get_redis as _get_redis  # noqa: PLC0415
    from app.ingestion.tasks import celery_app  # noqa: PLC0415

    act_result = await session.execute(select(Act).where(Act.slug == slug))
    act = act_result.scalar_one_or_none()
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Act with slug '{slug}' not found.",
        )

    r = _get_redis()
    key = _KEY_ACT.format(slug=slug)
    task_ids = list(await r.smembers(key))  # type: ignore[misc]

    if task_ids:
        celery_app.control.revoke(task_ids, terminate=True, signal="SIGTERM")
        await r.delete(key)
        # Remove from global set too
        await r.srem(_KEY_ALL, *task_ids)  # type: ignore[misc]

    # Mark running DB rows for this act as failed
    running_rows = list(
        (
            await session.execute(
                select(IngestionRun).where(
                    IngestionRun.act_id == act.id,
                    IngestionRun.status == "running",
                )
            )
        )
        .scalars()
        .all()
    )
    for run in running_rows:
        run.status = "failed"
        run.error = "Cancelled by operator"
    if running_rows:
        await session.commit()

    revoked = len(task_ids)
    logger.info("admin cancelled act ingestion", extra={"act_slug": slug, "revoked": revoked})
    return {"revoked": revoked, "message": f"Revoked {revoked} tasks for '{slug}'."}


@router.get("/llm", response_model=LLMOverrideResponse)
async def get_llm_override(
    settings: Settings = Depends(get_settings),
    redis: object = Depends(get_redis),
) -> LLMOverrideResponse:
    """Return the current effective LLM provider/model configuration.

    Args:
        settings: Application settings (env fallback).
        redis: Redis client.

    Returns:
        LLMOverrideResponse: Active provider, model, and source.
    """
    override = await llm_runtime.get_override(redis)
    if override is not None:
        return LLMOverrideResponse(
            provider=override.provider,
            model=override.model,
            source="override",
        )
    effective = await llm_runtime.resolve(redis, settings)
    return LLMOverrideResponse(
        provider=effective.provider,
        model=effective.model,
        source="env",
    )


@router.put("/llm", response_model=LLMOverrideResponse)
async def set_llm_override(
    body: LLMOverrideRequest,
    redis: object = Depends(get_redis),
) -> LLMOverrideResponse:
    """Write a provider/model override to Redis.

    Args:
        body: Provider and model to activate.
        redis: Redis client.

    Returns:
        LLMOverrideResponse: The newly active configuration.
    """
    provider: ProviderName = body.provider  # type: ignore[assignment]
    await llm_runtime.set_override(redis, provider=provider, model=body.model)
    return LLMOverrideResponse(
        provider=body.provider,
        model=body.model,
        source="override",
    )


@router.delete("/llm", status_code=204)
async def clear_llm_override(redis: object = Depends(get_redis)) -> None:
    """Remove the Redis LLM override key, reverting to env defaults.

    Args:
        redis: Redis client.
    """
    await llm_runtime.clear_override(redis)


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(session: AsyncSession = Depends(get_db)) -> MetricsResponse:
    """Return aggregated quality and cost metrics for the last 24 hours.

    Args:
        session: Async database session.

    Returns:
        MetricsResponse: Aggregated metrics.
    """
    window_result = await session.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE declined) AS declined_count,
                COUNT(*) FILTER (WHERE confidence_tier = 'HIGH') AS high_count,
                COUNT(*) FILTER (WHERE confidence_tier = 'MEDIUM') AS medium_count,
                COUNT(*) FILTER (WHERE confidence_tier = 'LOW') AS low_count,
                COUNT(*) FILTER (WHERE cached) AS cached_count,
                COUNT(*) FILTER (WHERE degraded) AS degraded_count,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                    AS p95_latency,
                COALESCE(SUM(cost_usd), 0) AS daily_spend
            FROM queries
            WHERE created_at >= now() - interval '24 hours'
        """)
    )
    row = window_result.fetchone()

    total = int(row.total) if row else 0
    declined = int(row.declined_count) if row else 0
    high = int(row.high_count) if row else 0
    medium = int(row.medium_count) if row else 0
    low = int(row.low_count) if row else 0
    cached = int(row.cached_count) if row else 0
    degraded_count = int(row.degraded_count) if row else 0
    p95 = float(row.p95_latency) if row and row.p95_latency is not None else None
    spend = float(row.daily_spend) if row else 0.0

    fb_result = await session.execute(
        text("SELECT COUNT(*) FROM feedback WHERE created_at >= now() - interval '24 hours'")
    )
    fb_count = int(fb_result.scalar() or 0)

    return MetricsResponse(
        total_queries=total,
        decline_rate=declined / total if total else 0.0,
        confidence_breakdown=ConfidenceBreakdown(HIGH=high, MEDIUM=medium, LOW=low),
        cache_hit_rate=cached / total if total else 0.0,
        degraded_rate=degraded_count / total if total else 0.0,
        p95_latency_ms=p95,
        daily_spend_usd=spend,
        feedback_count=fb_count,
    )


@router.get("/queries", response_model=RecentQueriesResponse)
async def recent_queries(
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
) -> RecentQueriesResponse:
    """Return the most recent queries and total count.

    Args:
        limit: Maximum number of queries to return (default 50, max 200).
        session: Async database session.

    Returns:
        RecentQueriesResponse: Recent queries and total.
    """
    limit = min(limit, 200)

    rows_result = await session.execute(
        select(Query).order_by(Query.created_at.desc()).limit(limit)
    )
    rows = list(rows_result.scalars().all())

    total_result = await session.execute(select(func.count(Query.id)))
    total = int(total_result.scalar() or 0)

    queries = [
        RecentQuery(
            id=str(q.id),
            query_text=q.query_text[:200],
            detected_language=q.detected_language,
            declined=q.declined,
            confidence_tier=q.confidence_tier,
            cached=q.cached,
            degraded=q.degraded,
            latency_ms=q.latency_ms,
            created_at=q.created_at,
        )
        for q in rows
    ]

    return RecentQueriesResponse(queries=queries, total=total)
