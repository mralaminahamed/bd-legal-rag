# Author: Al Amin Ahamed
"""Seed simulated (succeeded) ingestion runs for all registered Acts.

Creates one BN and one EN ``ingestion_runs`` record per Act with realistic
provision and chunk counts derived from the seeded corpus.  Idempotent: skips
acts that already have a run for the given language.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Act, Chunk, IngestionRun
from app.seeders.base import Seeder


class IngestionRunsSeeder(Seeder):
    """Seed one ``succeeded`` ingestion run per (Act, language).

    Counts are derived from chunks already in the database so the numbers
    reflect the actual seeded corpus size.
    """

    name = "ingestion_runs"
    depends_on = ["corpus"]
    truncate_sql = ["TRUNCATE TABLE ingestion_runs CASCADE"]

    async def run(self, db: AsyncSession, *, count: int) -> int:  # noqa: ARG002
        """Insert succeeded ingestion runs for every (act, language) pair.

        Args:
            db: Active async database session.
            count: Unused — one run per (act, language) is always created.

        Returns:
            int: Number of run records inserted.
        """
        acts_result = await db.execute(select(Act))
        acts: list[Act] = list(acts_result.scalars().all())
        if not acts:
            raise RuntimeError("acts must be seeded before ingestion_runs")

        inserted = 0
        # Stagger run timestamps to look realistic in the dashboard
        base_dt = datetime(2026, 5, 31, 10, 0, 0, tzinfo=UTC)

        for i, act in enumerate(acts):
            for j, lang in enumerate(("bn", "en")):
                # Idempotent check
                existing = await db.execute(
                    select(IngestionRun).where(
                        IngestionRun.act_id == act.id,
                        IngestionRun.language == lang,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                # Count actual seeded chunks for this act+language
                chunk_count_result = await db.execute(
                    select(func.count(Chunk.id)).where(
                        Chunk.act_id == act.id,
                        Chunk.language == lang,
                    )
                )
                chunk_count: int = chunk_count_result.scalar_one() or 0
                # Sections = chunks (one chunk per revision in corpus seeder)
                provision_count = chunk_count

                started = base_dt + timedelta(hours=i * 3 + j)
                finished = started + timedelta(minutes=12 + i)

                run = IngestionRun(
                    id=uuid.uuid4(),
                    act_id=act.id,
                    language=lang,
                    status="succeeded",
                    started_at=started,
                    finished_at=finished,
                    provisions_processed=provision_count,
                    chunks_created=chunk_count,
                    error=None,
                )
                db.add(run)
                inserted += 1

        await db.flush()
        return inserted
