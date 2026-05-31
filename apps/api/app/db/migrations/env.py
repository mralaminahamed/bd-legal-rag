"""Alembic migration environment (async).

Drives migrations against the async engine. The database URL is taken from the
application configuration (NFR-MN-4), and the target metadata is the declarative
``Base`` so future autogenerate runs compare against the live models.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from app.config import get_settings
from app.db.models import Base
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the async database URL from application configuration.

    Returns:
        str: The SQLAlchemy async DSN for PostgreSQL.
    """
    return get_settings().database_dsn


def run_migrations_offline() -> None:
    """Run migrations in offline mode, emitting SQL against a URL only."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    """Configure the context against a live connection and run migrations.

    Args:
        connection: The synchronous connection facade provided by ``run_sync``.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in online mode against the async engine."""
    engine = create_async_engine(_database_url(), poolclass=None)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
