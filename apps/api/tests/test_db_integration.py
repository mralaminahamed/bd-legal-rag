"""Database integration tests: schema, HNSW retrieval, and bootstrap.

All tests are guarded by a ``database_available()`` check and skip cleanly when
no migrated PostgreSQL+pgvector database is reachable. This keeps the unit-test
run fast and offline while the integration path exercises the live schema.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest
from app.db.engine import get_sessionmaker
from app.db.models import Act, Chunk, Provision, ProvisionRevision

from tests.conftest import database_available


@pytest.fixture
async def db_session():  # type: ignore[no-untyped-def]
    """Yield a session rolled back after the test so the DB stays clean."""
    if not await database_available():
        pytest.skip("no migrated PostgreSQL+pgvector database reachable")

    async with get_sessionmaker()() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.mark.asyncio
async def test_act_insert_and_retrieve(db_session) -> None:  # type: ignore[no-untyped-def]
    """An Act row can be inserted and read back by slug."""
    act = Act(
        slug="test-act-2026",
        short_name="Test Act 2026",
        full_name_en="The Test Act, 2026",
        full_name_bn="পরীক্ষামূলক আইন, ২০২৬",
        act_number="I",
        act_year=2026,
        status="in_force",
    )
    db_session.add(act)
    await db_session.flush()

    from sqlalchemy import select

    result = await db_session.execute(select(Act).where(Act.slug == "test-act-2026"))
    row = result.scalar_one()
    assert row.full_name_bn == "পরীক্ষামূলক আইন, ২০২৬"
    assert row.act_year == 2026


@pytest.mark.asyncio
async def test_chunk_hnsw_cosine_retrieval(db_session) -> None:  # type: ignore[no-untyped-def]
    """A chunk inserted with a known embedding is returned by HNSW cosine query."""
    from sqlalchemy import text

    # --- scaffold the statutory tree ---
    act = Act(
        slug="hnsw-test-act",
        short_name="HNSW Test Act",
        full_name_en="The HNSW Test Act, 2026",
        full_name_bn="HNSW পরীক্ষা আইন, ২০২৬",
        act_number="II",
        act_year=2026,
        status="in_force",
    )
    db_session.add(act)
    await db_session.flush()

    provision = Provision(
        act_id=act.id,
        kind="section",
        number="1",
        title="Test section",
        sort_path="1",
    )
    db_session.add(provision)
    await db_session.flush()

    revision = ProvisionRevision(
        provision_id=provision.id,
        language="en",
        translation_status="reference_translation",
        text="This is a test provision for HNSW indexing.",
        effective_from=date(2026, 1, 1),
        content_hash=hashlib.sha256(b"test").hexdigest(),
        source_url="https://bdlaws.minlaw.gov.bd/test",
    )
    db_session.add(revision)
    await db_session.flush()

    # Build a simple deterministic 1024-dim vector.
    dims = 1024
    embedding = [0.001] * dims
    embedding[0] = 1.0
    embedding_str = f"[{','.join(str(v) for v in embedding)}]"

    chunk = Chunk(
        revision_id=revision.id,
        provision_id=provision.id,
        act_id=act.id,
        chunk_index=0,
        language="en",
        hierarchy_path="HNSW Test Act > Section 1 (Test section)",
        content="This is a test provision for HNSW indexing.",
        token_count=9,
        embedding=embedding,
    )
    db_session.add(chunk)
    await db_session.flush()

    # HNSW cosine query — the inserted chunk must appear in the result.
    rows = (
        await db_session.execute(
            text(f"SELECT id FROM chunks ORDER BY embedding <=> '{embedding_str}' LIMIT 5")
        )
    ).fetchall()

    returned_ids = [row[0] for row in rows]
    assert chunk.id in returned_ids, "inserted chunk not found in HNSW cosine result"


@pytest.mark.asyncio
async def test_effective_date_index_exists(db_session) -> None:  # type: ignore[no-untyped-def]
    """The composite effective-date index exists on provision_revisions."""
    from sqlalchemy import text

    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'provision_revisions' "
            "AND indexname = 'provision_revisions_effective'"
        )
    )
    assert result.fetchone() is not None, "provision_revisions_effective index missing"


@pytest.mark.asyncio
async def test_disclaimer_version_not_null_enforced(db_session) -> None:  # type: ignore[no-untyped-def]
    """Inserting a query row without disclaimer_version raises IntegrityError."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO queries "
                "(correlation_id, query_text, disclaimer_version) "
                "VALUES ('corr-1', 'test?', NULL)"
            )
        )


@pytest.mark.asyncio
async def test_bootstrap_seeds_five_acts(db_session) -> None:  # type: ignore[no-untyped-def]
    """Bootstrap upserts all five v1.0 Acts from config/acts/*.yaml."""
    from app.ingestion.registry import bootstrap, list_acts

    await bootstrap(db_session)
    acts = await list_acts(db_session)
    slugs = {a.slug for a in acts}

    expected = {
        "companies-act-1994",
        "income-tax-act-2023",
        "vat-sd-act-2012",
        "labour-act-2006",
        "digital-security-act-2018",
    }
    assert expected.issubset(slugs), f"missing Acts: {expected - slugs}"


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent(db_session) -> None:  # type: ignore[no-untyped-def]
    """Running bootstrap twice does not raise and does not duplicate rows."""
    from app.ingestion.registry import bootstrap
    from sqlalchemy import func, select

    await bootstrap(db_session)
    await bootstrap(db_session)

    count_result = await db_session.execute(
        select(func.count()).select_from(Act).where(Act.slug == "labour-act-2006")
    )
    assert count_result.scalar() == 1
