"""Feedback analysis report — surface low-quality responses for prompt iteration.

Usage (from apps/api/):
    uv run python -m app.tools.feedback_report
    uv run python -m app.tools.feedback_report --rating not_helpful
    uv run python -m app.tools.feedback_report --limit 20

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import argparse
import asyncio
import textwrap

from sqlalchemy import select

from app.db.engine import session_scope
from app.db.models import Feedback, Query


async def run(rating_filter: str | None, limit: int) -> None:
    """Print feedback report to stdout.

    Args:
        rating_filter: Only show this rating (``not_helpful``, ``out_of_scope``,
            ``helpful``). None shows all non-helpful ratings.
        limit: Maximum number of entries to print.
    """
    async with session_scope() as session:
        stmt = (
            select(Feedback, Query)
            .join(Query, Query.id == Feedback.query_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        if rating_filter:
            stmt = stmt.where(Feedback.rating == rating_filter)
        else:
            stmt = stmt.where(Feedback.rating.in_(["not_helpful", "out_of_scope"]))

        rows = (await session.execute(stmt)).all()

    if not rows:
        print("No matching feedback found.")
        return

    separator = "=" * 70
    filt = rating_filter or "not_helpful+out_of_scope"
    print(f"\n{separator}")
    print(f"FEEDBACK REPORT  ({len(rows)} entries, filter={filt})")
    print(f"{separator}\n")

    dash = "-" * 70
    for fb, q in rows:
        ts = fb.created_at.strftime("%Y-%m-%d %H:%M")
        print(f"[{fb.rating.upper()}]  {ts}  query_id={q.id}")
        lang = q.detected_language or "?"
        print(f"Lang: {lang}  |  Declined: {q.declined}  |  Degraded: {q.degraded}")
        print(f"QUESTION: {q.query_text}")
        if q.response_text:
            preview = textwrap.shorten(q.response_text, width=300, placeholder="...")
            print(f"RESPONSE: {preview}")
        if fb.comment:
            print(f"COMMENT:  {fb.comment}")
        print(dash)


def main() -> None:
    """Entry point for ``python -m app.tools.feedback_report``.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Surface low-quality responses for prompt analysis."
    )
    parser.add_argument("--rating", choices=["helpful", "not_helpful", "out_of_scope"],
                        help="Filter by rating (default: not_helpful + out_of_scope)")
    parser.add_argument("--limit", type=int, default=20, help="Max entries (default: 20)")
    args = parser.parse_args()
    asyncio.run(run(args.rating, args.limit))


if __name__ == "__main__":
    main()
