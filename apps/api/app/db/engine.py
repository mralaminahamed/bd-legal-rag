"""Async database engine and session management.

Owns the single pooled SQLAlchemy 2.0 async engine for the process and the
``async_sessionmaker`` built on it. Two access patterns are exposed: an
``async`` generator dependency for FastAPI request handlers
(:func:`get_session`) and an ``async`` context manager for Celery tasks and
scripts (:func:`session_scope`). A connection is never opened or closed per
request; both helpers draw from the pool.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide pooled async engine.

    Built once and memoised so the connection pool is shared across the API,
    workers, and beat. Pool sizing comes from configuration defaults and uses
    ``pool_pre_ping`` to recover from severed connections transparently.

    Returns:
        AsyncEngine: The shared asyncpg-backed engine.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_dsn,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory bound to the shared engine.

    Returns:
        async_sessionmaker[AsyncSession]: Factory producing ``AsyncSession``
        objects that do not expire attributes on commit.
    """
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session for FastAPI dependencies.

    The session is closed when the request completes. Transaction control is
    left to the handler so reads incur no transaction overhead and writes commit
    explicitly.

    Yields:
        AsyncSession: A session drawn from the pool for the request's lifetime.
    """
    async with get_sessionmaker()() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional session scope for Celery tasks and scripts.

    Commits on clean exit and rolls back on any exception, then always closes
    the session. Use this outside the request lifecycle where no FastAPI
    dependency is available.

    Yields:
        AsyncSession: A session whose work is committed on success and rolled
        back on failure.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_worker_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return a session factory using NullPool — safe for Celery fork workers.

    Celery fork workers inherit the parent process's pooled engine, whose
    asyncpg connections are bound to the parent event loop.  Using NullPool
    avoids the pool entirely: each ``connect()`` opens a fresh connection and
    closes it when the session ends.  There is no connection reuse across
    ``asyncio.run()`` calls so the event-loop mismatch cannot occur.

    Returns:
        async_sessionmaker[AsyncSession]: Session factory with NullPool engine.
    """
    settings = get_settings()
    worker_engine = create_async_engine(
        settings.database_dsn,
        poolclass=NullPool,
        future=True,
    )
    return async_sessionmaker(
        bind=worker_engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_engine() -> None:
    """Dispose the engine and close all pooled connections.

    Called on application shutdown so the pool is released cleanly.
    """
    await get_engine().dispose()
