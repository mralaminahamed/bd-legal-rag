# Author: Al Amin Ahamed
"""Abstract base seeder.

Pattern: Laravel-style seeders. Each seeder is idempotent — re-running on
populated tables uses upsert or skip-if-exists semantics. Use ``--fresh`` to
truncate first.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class Seeder(ABC):
    """Abstract base for table seeders.

    Subclasses declare:
    - ``name``: short identifier matching the ``--table`` CLI flag.
    - ``depends_on``: seeder names that must run first.
    - ``truncate_sql``: SQL statements executed when ``--fresh`` is passed
      (listed in dependency order; the CLI reverses them automatically).
    """

    name: str = ""
    depends_on: list[str] = []
    truncate_sql: list[str] = []

    @abstractmethod
    async def run(self, db: AsyncSession, *, count: int) -> int:
        """Seed the table and return the number of rows inserted or upserted.

        Args:
            db: Active async database session (do not commit — the caller does).
            count: Per-seeder row count override (0 = use seeder default).

        Returns:
            int: Rows inserted or upserted.
        """

    async def truncate(self, db: AsyncSession) -> None:
        """Execute every ``truncate_sql`` statement in order.

        Args:
            db: Active async database session.
        """
        from sqlalchemy import text as _text  # noqa: PLC0415

        for stmt in self.truncate_sql:
            await db.execute(_text(stmt))
