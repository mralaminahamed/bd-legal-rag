"""Tests for the ingestion Celery tasks.

All external dependencies (network, database) are mocked or replaced by
in-memory doubles. Tests verify hash-skip behaviour, isolation between sibling
tasks, IngestionRun row creation, and IngestSummary correctness.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import Act
from app.ingestion.crawler import CrawlResult
from app.ingestion.summary import IngestSummary
from app.ingestion.tasks import ingest_act_language

from tests.conftest import database_available

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_SECTION_HTML = """
<html><body>
<div class="lawCon">
  <div class="section">
    <div class="sec_head">103. Weekly holiday</div>
    <div class="sec_content">Every worker shall be given at least one day off per week.</div>
  </div>
</div>
</body></html>
"""

_UPDATED_HTML = """
<html><body>
<div class="lawCon">
  <div class="section">
    <div class="sec_head">103. Weekly holiday</div>
    <div class="sec_content">Every worker shall be given at least
one and a half days off per week.</div>
  </div>
</div>
</body></html>
"""


def _make_crawl_result(html: str, url: str = "https://bdlaws.minlaw.gov.bd/test") -> CrawlResult:
    """Build a CrawlResult with the given HTML."""
    return CrawlResult(
        url=url,
        html=html,
        language="en",
        act_slug="labour-act-2006",
        fetched_at=datetime.now(UTC),
        etag=None,
        last_modified=None,
        not_modified=False,
    )


def _make_not_modified_result() -> CrawlResult:
    """Build a not_modified CrawlResult."""
    return CrawlResult(
        url="https://bdlaws.minlaw.gov.bd/test",
        html="",
        language="en",
        act_slug="labour-act-2006",
        fetched_at=datetime.now(UTC),
        etag='"abc"',
        last_modified=None,
        not_modified=True,
    )


# ---------------------------------------------------------------------------
# Integration tests (require a migrated DB)
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session_factory():  # type: ignore[no-untyped-def]
    """Yield an async sessionmaker against the live DB or skip."""
    if not await database_available():
        pytest.skip("no migrated PostgreSQL+pgvector database reachable")
    from app.db.engine import get_sessionmaker

    yield get_sessionmaker()


@pytest.fixture
async def act_row(db_session_factory):  # type: ignore[no-untyped-def]
    """Insert a test Act and yield it; clean up after."""
    factory = db_session_factory
    act_id = uuid.uuid4()
    async with factory() as session:
        act = Act(
            id=act_id,
            slug="phase2-test-act",
            short_name="Phase 2 Test Act",
            full_name_en="The Phase 2 Test Act, 2026",
            full_name_bn="ফেজ ২ পরীক্ষা আইন, ২০২৬",
            act_number="TEST",
            act_year=2026,
            status="in_force",
        )
        session.add(act)
        await session.commit()
    yield act_id
    async with factory() as session:
        a = await session.get(Act, act_id)
        if a is not None:
            await session.delete(a)
            await session.commit()


@pytest.mark.asyncio
async def test_ingest_creates_provisions(act_row, db_session_factory) -> None:  # type: ignore[no-untyped-def]
    """Ingestion populates provision_revisions with text and a content_hash."""
    from app.db.models import ProvisionRevision
    from sqlalchemy import select

    summary = await ingest_act_language(
        act_row,
        "en",
        sessionmaker=db_session_factory,
        crawl_result=_make_crawl_result(_SECTION_HTML),
    )

    assert summary.status == "succeeded"
    assert summary.provisions_new > 0

    async with db_session_factory() as session:
        revisions = (
            (
                await session.execute(
                    select(ProvisionRevision)
                    .join(ProvisionRevision.provision)
                    .where(
                        # type: ignore[attr-defined]
                        ProvisionRevision.language == "en"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(revisions) > 0
        assert all(rev.content_hash for rev in revisions)


@pytest.mark.asyncio
async def test_hash_skip_on_unchanged_content(act_row, db_session_factory) -> None:  # type: ignore[no-untyped-def]
    """Re-ingesting identical HTML skips revision creation (FR-IN-4)."""
    crawl = _make_crawl_result(_SECTION_HTML)

    first = await ingest_act_language(
        act_row, "en", sessionmaker=db_session_factory, crawl_result=crawl
    )
    assert first.provisions_new > 0

    second = await ingest_act_language(
        act_row, "en", sessionmaker=db_session_factory, crawl_result=crawl
    )
    assert second.provisions_new == 0
    assert second.provisions_updated == 0
    assert second.provisions_unchanged == first.provisions_new


@pytest.mark.asyncio
async def test_updated_text_creates_new_revision(act_row, db_session_factory) -> None:  # type: ignore[no-untyped-def]
    """Ingesting changed HTML creates a new revision and closes the prior one."""
    from app.db.models import ProvisionRevision
    from sqlalchemy import select

    await ingest_act_language(
        act_row,
        "en",
        sessionmaker=db_session_factory,
        crawl_result=_make_crawl_result(_SECTION_HTML),
    )
    summary = await ingest_act_language(
        act_row,
        "en",
        sessionmaker=db_session_factory,
        crawl_result=_make_crawl_result(_UPDATED_HTML),
    )

    assert summary.provisions_updated > 0

    async with db_session_factory() as session:
        all_revisions = (await session.execute(select(ProvisionRevision))).scalars().all()
        # Old revision should be closed (effective_to set)
        closed = [r for r in all_revisions if r.effective_to is not None]
        assert len(closed) > 0


@pytest.mark.asyncio
async def test_not_modified_returns_success_with_zero_counts(act_row, db_session_factory) -> None:  # type: ignore[no-untyped-def]
    """304 Not Modified result returns succeeded with no provision changes."""
    summary = await ingest_act_language(
        act_row,
        "en",
        sessionmaker=db_session_factory,
        crawl_result=_make_not_modified_result(),
    )

    assert summary.status == "succeeded"
    assert summary.provisions_new == 0
    assert summary.provisions_updated == 0


@pytest.mark.asyncio
async def test_failure_does_not_affect_siblings(act_row, db_session_factory) -> None:  # type: ignore[no-untyped-def]
    """A failure in one (act, language) task does not abort the other (FR-IN-5)."""
    bad_crawl = _make_crawl_result("<<<invalid html", "https://bad-url")
    # This should fail gracefully
    summary_bad = await ingest_act_language(
        act_row, "en", sessionmaker=db_session_factory, crawl_result=bad_crawl
    )
    # The task itself records the failure but doesn't propagate an exception
    # (it catches all exceptions and returns IngestSummary with status="failed")
    assert isinstance(summary_bad, IngestSummary)

    # The sibling BN task runs independently — simulate a successful BN ingest
    bn_crawl = CrawlResult(
        url="https://bdlaws.minlaw.gov.bd/test-bn",
        html=_SECTION_HTML,
        language="bn",
        act_slug="phase2-test-act",
        fetched_at=datetime.now(UTC),
        etag=None,
        last_modified=None,
        not_modified=False,
    )
    summary_bn = await ingest_act_language(
        act_row, "bn", sessionmaker=db_session_factory, crawl_result=bn_crawl
    )
    assert isinstance(summary_bn, IngestSummary)


@pytest.mark.asyncio
async def test_missing_act_returns_failed_summary(db_session_factory) -> None:  # type: ignore[no-untyped-def]
    """Ingesting a non-existent Act returns a failed IngestSummary — no exception."""
    fake_id = uuid.uuid4()
    summary = await ingest_act_language(fake_id, "en", sessionmaker=db_session_factory)
    assert summary.status == "failed"
    assert summary.error is not None


# ---------------------------------------------------------------------------
# Phase 3 — chunk + embed wiring (FR-PR-3, FR-PR-4, FR-PR-5)
# ---------------------------------------------------------------------------

_TWO_SECTION_HTML = """
<html><body>
<div class="lawCon">
  <div class="section">
    <div class="sec_head">101. Annual leave</div>
    <div class="sec_content">Every worker shall be entitled to annual leave with pay.</div>
  </div>
  <div class="section">
    <div class="sec_head">103. Weekly holiday</div>
    <div class="sec_content">Every worker shall be given at least one day off per week.</div>
  </div>
</div>
</body></html>
"""

_TWO_SECTION_HTML_UPDATED_101 = """
<html><body>
<div class="lawCon">
  <div class="section">
    <div class="sec_head">101. Annual leave</div>
    <div class="sec_content">Every worker shall be entitled to annual leave
with full pay and benefits.</div>
  </div>
  <div class="section">
    <div class="sec_head">103. Weekly holiday</div>
    <div class="sec_content">Every worker shall be given at least one day off per week.</div>
  </div>
</div>
</body></html>
"""


def _make_mock_cohere_client() -> tuple[object, object]:
    """Return (mock_cls, mock_client) that returns correctly-sized vectors per call."""
    from unittest.mock import AsyncMock, MagicMock

    call_count = 0

    async def fake_embed(**kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        n = len(kwargs["texts"])  # type: ignore[arg-type]
        r = MagicMock()
        r.embeddings.float_ = [[float(call_count) / 10.0] * 1024 for _ in range(n)]
        return r

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=fake_embed)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls, mock_client


@pytest.mark.asyncio
async def test_ingestion_creates_chunks_with_embeddings(  # type: ignore[no-untyped-def]
    act_row, db_session_factory, monkeypatch
) -> None:
    """After ingestion, chunks has non-null 1024-dim embeddings (Phase 3 acceptance)."""
    from unittest.mock import patch

    from app.config import get_settings
    from app.db.models import Chunk
    from sqlalchemy import select

    monkeypatch.setenv("BDRAG_COHERE_API_KEY", "test-key-phase3")
    get_settings.cache_clear()

    mock_cls, _ = _make_mock_cohere_client()

    try:
        with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
            summary = await ingest_act_language(
                act_row,
                "en",
                sessionmaker=db_session_factory,
                crawl_result=_make_crawl_result(_SECTION_HTML),
            )
    finally:
        get_settings.cache_clear()

    assert summary.status == "succeeded"
    assert summary.chunks_created > 0

    async with db_session_factory() as session:
        chunks = (await session.execute(select(Chunk))).scalars().all()
    assert len(chunks) > 0
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(len(chunk.embedding) == 1024 for chunk in chunks)
    assert all(chunk.content_tsv is not None for chunk in chunks)
    assert all(chunk.hierarchy_path for chunk in chunks)


@pytest.mark.asyncio
async def test_hierarchy_path_contains_section_label(  # type: ignore[no-untyped-def]
    act_row, db_session_factory, monkeypatch
) -> None:
    """Chunks carry hierarchy_path with statutory breadcrumb (architecture §2.3)."""
    from unittest.mock import patch

    from app.config import get_settings
    from app.db.models import Chunk
    from sqlalchemy import select

    monkeypatch.setenv("BDRAG_COHERE_API_KEY", "test-key-phase3")
    get_settings.cache_clear()

    mock_cls, _ = _make_mock_cohere_client()

    try:
        with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
            await ingest_act_language(
                act_row,
                "en",
                sessionmaker=db_session_factory,
                crawl_result=_make_crawl_result(_SECTION_HTML),
            )
    finally:
        get_settings.cache_clear()

    async with db_session_factory() as session:
        chunks = (await session.execute(select(Chunk))).scalars().all()

    assert len(chunks) > 0
    for chunk in chunks:
        assert "Section" in chunk.hierarchy_path or "section" in chunk.hierarchy_path.lower()


@pytest.mark.asyncio
async def test_reindex_changed_revision_leaves_sibling_chunks_untouched(
    act_row, db_session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """Re-indexing one changed revision does not delete sibling-revision chunks (FR-PR-3)."""
    from unittest.mock import patch

    from app.config import get_settings
    from app.db.models import Chunk
    from sqlalchemy import select

    monkeypatch.setenv("BDRAG_COHERE_API_KEY", "test-key-phase3")
    get_settings.cache_clear()

    mock_cls, _ = _make_mock_cohere_client()

    try:
        with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
            await ingest_act_language(
                act_row,
                "en",
                sessionmaker=db_session_factory,
                crawl_result=_make_crawl_result(_TWO_SECTION_HTML),
            )

        async with db_session_factory() as session:
            chunks_after_first = (await session.execute(select(Chunk))).scalars().all()
        chunk_ids_after_first = {c.id for c in chunks_after_first}
        assert len(chunk_ids_after_first) >= 2, "expected ≥2 chunks (one per section)"

        chunks_103 = [c for c in chunks_after_first if "103" in c.hierarchy_path]
        assert chunks_103, "expected a chunk for section 103"
        ids_103 = {c.id for c in chunks_103}

        mock_cls2, _ = _make_mock_cohere_client()
        with patch("app.processing.embedder.cohere.AsyncClient", mock_cls2):
            await ingest_act_language(
                act_row,
                "en",
                sessionmaker=db_session_factory,
                crawl_result=_make_crawl_result(_TWO_SECTION_HTML_UPDATED_101),
            )
    finally:
        get_settings.cache_clear()

    async with db_session_factory() as session:
        chunks_after_second = (await session.execute(select(Chunk))).scalars().all()

    ids_after_second = {c.id for c in chunks_after_second}
    assert ids_103.issubset(ids_after_second), (
        "section 103 chunks were wrongly deleted during re-index of section 101"
    )


@pytest.mark.asyncio
async def test_hash_skip_does_not_recreate_chunks(act_row, db_session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Re-ingesting identical HTML preserves existing chunk IDs (hash-skip, FR-IN-4)."""
    from unittest.mock import patch

    from app.config import get_settings
    from app.db.models import Chunk
    from sqlalchemy import select

    monkeypatch.setenv("BDRAG_COHERE_API_KEY", "test-key-phase3")
    get_settings.cache_clear()

    crawl = _make_crawl_result(_SECTION_HTML)
    mock_cls, _ = _make_mock_cohere_client()

    try:
        with patch("app.processing.embedder.cohere.AsyncClient", mock_cls):
            await ingest_act_language(
                act_row, "en", sessionmaker=db_session_factory, crawl_result=crawl
            )

        async with db_session_factory() as session:
            ids_first = {c.id for c in (await session.execute(select(Chunk))).scalars().all()}

        mock_cls2, _ = _make_mock_cohere_client()
        with patch("app.processing.embedder.cohere.AsyncClient", mock_cls2):
            summary2 = await ingest_act_language(
                act_row, "en", sessionmaker=db_session_factory, crawl_result=crawl
            )
    finally:
        get_settings.cache_clear()

    assert summary2.chunks_created == 0

    async with db_session_factory() as session:
        ids_second = {c.id for c in (await session.execute(select(Chunk))).scalars().all()}
    assert ids_first == ids_second, "chunk IDs changed on identical re-ingest"
