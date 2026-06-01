# Author: Al Amin Ahamed
"""Seed sample feedback entries on non-declined queries.

Seeds one feedback record per non-declined, non-cached query using a
realistic distribution of ratings. Idempotent: skips queries that already
have feedback.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, Query
from app.seeders.base import Seeder

# Realistic distribution skewed towards "helpful"
_RATINGS = [
    "helpful",
    "helpful",
    "helpful",
    "helpful",
    "not_helpful",
    "wrong_citation",
    "helpful",
    "out_of_scope",
    "helpful",
]

_COMMENTS: list[str | None] = [
    "Clear and well-cited answer.",
    "Helped understand the provision.",
    None,
    "Citation points to wrong section.",
    "Answer was incomplete.",
    None,
    "Excellent bilingual response.",
    "The retrieved section does not match my question.",
    None,
]


class FeedbackSeeder(Seeder):
    """Seed feedback rows for answered (non-declined) queries."""

    name = "feedback"
    depends_on = ["queries"]
    truncate_sql = ["TRUNCATE TABLE feedback CASCADE"]

    async def run(self, db: AsyncSession, *, count: int) -> int:  # noqa: ARG002
        """Seed one feedback per answered query.

        Args:
            db: Active async database session.
            count: Unused — one feedback per answered query.

        Returns:
            int: Number of feedback rows inserted.
        """
        answered_result = await db.execute(
            select(Query).where(
                Query.declined.is_(False),
                Query.cached.is_(False),
            )
        )
        answered: list[Query] = list(answered_result.scalars().all())

        rng = random.Random(42)  # noqa: S311
        inserted = 0

        for query in answered:
            existing = await db.execute(
                select(Feedback).where(Feedback.query_id == query.id)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            rating = rng.choice(_RATINGS)
            comment = rng.choice(_COMMENTS)

            fb = Feedback(
                id=uuid.uuid4(),
                query_id=query.id,
                rating=rating,
                comment=comment,
            )
            db.add(fb)
            inserted += 1

        await db.flush()
        return inserted
