"""Celery application and ingestion tasks.

Defines the configured Celery application used by the ``worker`` and ``beat``
services and the ingestion tasks. One task per ``(act, language)`` pair records
an ``ingestion_runs`` row; a content hash per provision revision skips unchanged
content (FR-IN-4); and a failure in one task never aborts its siblings (FR-IN-5).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from celery import Celery
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.engine import get_sessionmaker
from app.db.models import Act, IngestionRun, Provision, ProvisionRevision
from app.ingestion.amendments import latest_amendment
from app.ingestion.crawler import BdlawsFetchError, CrawlResult, fetch_act_page
from app.ingestion.parser import ProvisionNode, parse_act_page
from app.ingestion.registry import get_source_urls
from app.ingestion.summary import IngestSummary

logger = logging.getLogger(__name__)

_settings = get_settings()
_redis_url = str(_settings.redis_dsn)

celery_app = Celery(
    "bd_legal_rag",
    broker=_redis_url,
    backend=_redis_url,
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)


def _content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of provision text (FR-IN-4).

    Args:
        text: Normalised provision text.

    Returns:
        str: Hex digest used to detect unchanged content.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sort_path(number: str, parent_sort_path: str | None) -> str:
    """Build the slash-delimited sort path for a provision.

    Args:
        number: The provision's statutory number.
        parent_sort_path: Parent's sort path, or ``None`` for top-level.

    Returns:
        str: The sort path (e.g. ``"1/103/2"``).
    """
    return f"{parent_sort_path}/{number}" if parent_sort_path else number


async def _upsert_provision(
    session: AsyncSession,
    act_id: uuid.UUID,
    node: ProvisionNode,
    parent_id: uuid.UUID | None,
    sort_path: str,
) -> uuid.UUID:
    """Upsert one Provision row and return its id.

    Args:
        session: Active async session.
        act_id: Owning Act id.
        node: The parsed provision node.
        parent_id: Parent provision id, or ``None`` for top-level.
        sort_path: Computed sort path.

    Returns:
        uuid.UUID: The provision id (new or existing).
    """
    stmt = (
        pg_insert(Provision)
        .values(
            act_id=act_id,
            parent_id=parent_id,
            kind=node.kind if node.kind != "act" else "section",
            number=node.number,
            title=node.title,
            sort_path=sort_path,
        )
        .on_conflict_do_update(
            index_elements=["act_id", "sort_path"],
            set_={"title": node.title, "number": node.number},
        )
        .returning(Provision.id)
    )
    result = await session.execute(stmt)
    row = result.fetchone()
    return uuid.UUID(str(row[0])) if row else uuid.uuid4()


async def _upsert_revision(
    session: AsyncSession,
    provision_id: uuid.UUID,
    node: ProvisionNode,
    language: str,
    source_url: str,
    fetched_at: datetime,
) -> str:
    """Upsert a ProvisionRevision row and return the change outcome.

    Returns ``"unchanged"`` when the content hash matches the existing revision,
    ``"new"`` when no prior revision existed, or ``"updated"`` when the text changed.

    Args:
        session: Active async session.
        provision_id: Owning provision id.
        node: The parsed provision node supplying text and dates.
        language: ``bn`` or ``en``.
        source_url: Source URL for this revision.
        fetched_at: Crawl timestamp.

    Returns:
        str: One of ``"new"``, ``"updated"``, or ``"unchanged"``.
    """
    text = node.text
    if not text:
        return "unchanged"

    digest = _content_hash(text)
    translation_status = "authoritative" if language == "bn" else "reference_translation"

    amendment = latest_amendment("", fetched_at)

    existing = (
        await session.execute(
            select(ProvisionRevision).where(
                ProvisionRevision.provision_id == provision_id,
                ProvisionRevision.language == language,
                ProvisionRevision.effective_to.is_(None),
            )
        )
    ).scalar_one_or_none()

    if existing is not None and existing.content_hash == digest:
        return "unchanged"

    effective_from = node.effective_from or amendment.effective_from or fetched_at.date()
    meta: dict[str, str] = {"provenance": amendment.provenance}

    if existing is not None:
        # Close the prior revision before inserting the new one.
        existing.effective_to = fetched_at.date()
        await session.flush()

    revision = ProvisionRevision(
        provision_id=provision_id,
        language=language,
        translation_status=translation_status,
        text=text,
        effective_from=effective_from,
        effective_to=None,
        amending_act_id=None,
        content_hash=digest,
        source_url=source_url,
    )
    # Store provenance in the jsonb metadata column (mapped as `meta`).
    revision.meta = meta  # type: ignore[attr-defined]
    session.add(revision)
    await session.flush()

    return "new" if existing is None else "updated"


async def _walk_tree(
    session: AsyncSession,
    act_id: uuid.UUID,
    nodes: tuple[ProvisionNode, ...],
    language: str,
    source_url: str,
    fetched_at: datetime,
    parent_id: uuid.UUID | None,
    parent_sort_path: str | None,
    counts: dict[str, int],
) -> None:
    """Recursively walk the ProvisionNode tree and upsert rows.

    Args:
        session: Active async session.
        act_id: Owning Act id.
        nodes: Child provision nodes to process.
        language: Language variant.
        source_url: Source URL carried to revisions.
        fetched_at: Crawl timestamp.
        parent_id: Parent provision id.
        parent_sort_path: Parent's sort path for building child paths.
        counts: Mutable counter dict (``new``, ``updated``, ``unchanged``).
    """
    for node in nodes:
        if node.kind == "act":
            await _walk_tree(
                session,
                act_id,
                node.children,
                language,
                source_url,
                fetched_at,
                parent_id,
                parent_sort_path,
                counts,
            )
            continue

        sort_path = _sort_path(node.number, parent_sort_path)
        provision_id = await _upsert_provision(session, act_id, node, parent_id, sort_path)

        if node.text:
            outcome = await _upsert_revision(
                session, provision_id, node, language, source_url, fetched_at
            )
            counts[outcome] = counts.get(outcome, 0) + 1

        if node.children:
            await _walk_tree(
                session,
                act_id,
                node.children,
                language,
                source_url,
                fetched_at,
                provision_id,
                sort_path,
                counts,
            )


async def ingest_act_language(
    act_id: uuid.UUID,
    language: Literal["bn", "en"],
    *,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    crawl_result: CrawlResult | None = None,
) -> IngestSummary:
    """Fetch, parse, and persist one ``(act, language)`` pair (FR-IN-*).

    A run row is created up front. Unchanged provision revisions are skipped
    by content hash (FR-IN-4). Failures are caught and recorded without
    propagating so sibling tasks are unaffected (FR-IN-5).

    Args:
        act_id: The Act to ingest.
        language: Language variant.
        sessionmaker: Optional session factory override (used by tests).
        crawl_result: Optional pre-fetched HTML (used by tests to avoid network).

    Returns:
        IngestSummary: Counts and status for this ingestion run.
    """
    factory = sessionmaker or get_sessionmaker()

    # --- Create the run row ---
    run_id: uuid.UUID | None = None
    async with factory() as session:
        act = await session.get(Act, act_id)
        if act is None:
            return IngestSummary(
                act_id=act_id,
                language=language,
                status="failed",
                error="Act not found",
            )
        run = IngestionRun(act_id=act_id, language=language, status="running")
        session.add(run)
        await session.commit()
        run_id = run.id

    new = updated = unchanged = 0
    try:
        # --- Crawl (or use supplied result) ---
        if crawl_result is None:
            sources = await get_source_urls(act.slug)
            source = next((s for s in sources if s.get("language") == language), None)
            if source is None:
                raise BdlawsFetchError(
                    f"no source_url configured for {act.slug} language={language}"
                )
            crawl_result = await fetch_act_page(source["source_url"], act.slug, language)

        if crawl_result.not_modified:
            async with factory() as session:
                run_row = await session.get(IngestionRun, run_id)
                if run_row is not None:
                    run_row.status = "succeeded"
                    run_row.finished_at = datetime.now(UTC)
                await session.commit()
            return IngestSummary(
                act_id=act_id,
                language=language,
                status="succeeded",
                provisions_unchanged=0,
            )

        fetched_at = crawl_result.fetched_at
        source_url = crawl_result.url

        # --- Parse ---
        parse_result = parse_act_page(crawl_result.html, source_url)
        if parse_result.warnings:
            for w in parse_result.warnings:
                logger.warning(
                    "parse warning for act",
                    extra={"act_slug": act.slug, "language": language, "msg": w.message},
                )

        # --- Persist ---
        counts: dict[str, int] = {}
        async with factory() as session:
            await _walk_tree(
                session,
                act_id,
                (parse_result.root,),
                language,
                source_url,
                fetched_at,
                None,
                None,
                counts,
            )
            await session.commit()

        new = counts.get("new", 0)
        updated = counts.get("updated", 0)
        unchanged = counts.get("unchanged", 0)

        # --- Update run row ---
        async with factory() as session:
            run_row = await session.get(IngestionRun, run_id)
            if run_row is not None:
                run_row.status = "succeeded"
                run_row.finished_at = datetime.now(UTC)
                run_row.provisions_processed = new + updated + unchanged
                run_row.chunks_created = 0  # Phase 3 wires embedding
            await session.commit()

    except Exception as exc:  # noqa: BLE001 — isolate per-(act,lang) failures (FR-IN-5)
        logger.warning(
            "ingestion failed",
            extra={"act_id": str(act_id), "language": language},
            exc_info=True,
        )
        if run_id is not None:
            async with factory() as session:
                run_row = await session.get(IngestionRun, run_id)
                if run_row is not None:
                    run_row.status = "failed"
                    run_row.finished_at = datetime.now(UTC)
                    run_row.error = str(exc)
                await session.commit()
        return IngestSummary(
            act_id=act_id,
            language=language,
            status="failed",
            error=str(exc),
        )

    return IngestSummary(
        act_id=act_id,
        language=language,
        status="succeeded",
        provisions_new=new,
        provisions_updated=updated,
        provisions_unchanged=unchanged,
    )


@celery_app.task(name="ingestion.ingest_act_language")
def ingest_act_language_task(act_id: str, language: str) -> dict[str, object]:
    """Celery entry point to ingest one ``(act, language)`` pair.

    Args:
        act_id: String UUID of the Act to ingest.
        language: Language variant (``bn`` or ``en``).

    Returns:
        dict[str, object]: The serialised :class:`IngestSummary`.
    """
    summary = asyncio.run(
        ingest_act_language(uuid.UUID(act_id), language)  # type: ignore[arg-type]
    )
    return summary.model_dump(mode="json")


@celery_app.task(name="ingestion.ingest_act")
def ingest_act_task(act_id: str) -> list[dict[str, object]]:
    """Celery entry point that fans out one task per language for an Act.

    Args:
        act_id: String UUID of the Act to ingest.

    Returns:
        list[dict[str, object]]: Dispatched task signatures.
    """
    for lang in ("bn", "en"):
        ingest_act_language_task.delay(act_id, lang)
    return [{"act_id": act_id, "language": lang} for lang in ("bn", "en")]
