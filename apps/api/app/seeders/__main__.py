# Author: Al Amin Ahamed
"""CLI entry-point for the BD Legal RAG seeder.

Run from ``apps/api/``:

    uv run python -m app.seeders                        # seed all tables
    uv run python -m app.seeders --table acts           # seed one table
    uv run python -m app.seeders --fresh                # truncate, then seed
    uv run python -m app.seeders --table queries --count 30

Seeder order (dependency-resolved):
    acts → corpus → ingestion_runs → queries → feedback

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys


async def _run_seed(*, table: str, fresh: bool, count: int) -> None:
    """Execute the requested seeders inside a database session.

    Args:
        table: Seeder name or ``"all"``.
        fresh: Whether to truncate before seeding.
        count: Per-seeder row-count override (0 = seeder default).
    """
    from app.db.engine import get_sessionmaker  # noqa: PLC0415
    from app.seeders.registry import SEEDERS, SEEDERS_BY_NAME  # noqa: PLC0415

    if table == "all":
        selected = SEEDERS
    elif table in SEEDERS_BY_NAME:
        selected = [SEEDERS_BY_NAME[table]]
    else:
        available = ["all", *SEEDERS_BY_NAME.keys()]
        print(f"Unknown table {table!r}. Available: {available}", file=sys.stderr)
        sys.exit(1)

    if fresh:
        print("⚠  --fresh: truncating tables (in reverse dependency order)...")

    async with get_sessionmaker()() as db:
        if fresh:
            for cls in reversed(selected):
                inst = cls()
                if inst.truncate_sql:
                    print(f"  truncate: {inst.name}")
                    await inst.truncate(db)
            await db.commit()

        for cls in selected:
            inst = cls()
            print(f"→ seed {inst.name}...", end="", flush=True)
            try:
                n = await inst.run(db, count=count)
                await db.commit()
                print(f" {n} rows")
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                print(f" FAILED: {exc}", file=sys.stderr)
                sys.exit(1)

    print("✓ seed complete")


def main() -> None:
    """Parse CLI arguments and dispatch to the async seeder runner."""
    parser = argparse.ArgumentParser(
        prog="python -m app.seeders",
        description="Seed sample data into the BD Legal RAG database.",
    )
    parser.add_argument(
        "--table",
        default="all",
        metavar="NAME",
        help="Seeder name (acts|corpus|ingestion_runs|queries|feedback) or 'all'.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Truncate tables before seeding (DESTRUCTIVE — never use in production).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        metavar="N",
        help="Per-seeder row count override (0 = seeder default; queries default=20).",
    )
    args = parser.parse_args()
    asyncio.run(_run_seed(table=args.table, fresh=args.fresh, count=args.count))


if __name__ == "__main__":
    main()
