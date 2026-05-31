"""Shared test fixtures.

Provides LRU-cache clearing between tests (so each async test gets its own
engine and Redis pool on its own event loop), a database-availability gate for
integration tests, and in-memory doubles for LLM providers.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _fresh_pooled_clients() -> Iterator[None]:
    """Rebuild the cached engine/Redis clients per test.

    Each async test runs on its own event loop; a pooled engine cached from a
    prior test is bound to that test's now-closed loop and would fail. Clearing
    the memoised factories ensures every test builds clients on its own loop.

    Yields:
        None: Control to the test body.
    """
    from app.db.engine import get_engine, get_sessionmaker
    from app.db.redis import get_redis

    for cached in (get_engine, get_sessionmaker, get_redis):
        cached.cache_clear()
    yield
    for cached in (get_engine, get_sessionmaker, get_redis):
        cached.cache_clear()


async def database_available() -> bool:
    """Report whether a migrated database is reachable.

    Returns:
        bool: ``True`` if the ``acts`` table can be queried.
    """
    from app.db.engine import get_sessionmaker

    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1 FROM acts LIMIT 0"))
        return True
    except Exception:
        return False
