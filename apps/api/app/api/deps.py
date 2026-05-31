"""FastAPI dependency providers.

Centrally defines reusable ``Depends``-compatible callables for database
sessions, Redis access, authentication, and rate limiting so individual route
modules stay free of connection and auth boilerplate.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.engine import get_session
from app.db.redis import get_redis as _get_redis_client


async def get_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncIterator[AsyncSession]:
    """Yield the request-scoped database session.

    Args:
        session: Session provided by the engine dependency.

    Yields:
        AsyncSession: Active session for the request lifetime.
    """
    yield session


async def get_redis() -> Redis:
    """Return the process-wide Redis client.

    Returns:
        Redis: The shared async Redis client.
    """
    return _get_redis_client()


async def require_admin(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce bearer-token authentication on admin endpoints (NFR-SC-2).

    Args:
        authorization: Value of the ``Authorization`` request header.
        settings: Application settings supplying the expected token.

    Raises:
        HTTPException: 401 when the header is absent or the token is incorrect.
    """
    if settings.admin_bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin bearer token not configured",
        )
    expected = f"Bearer {settings.admin_bearer_token.get_secret_value()}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
        )


async def rate_limit(request: Request) -> None:
    """Apply per-hashed-IP rate limiting using Redis (NFR-SC-2).

    The IP is SHA-256 hashed before use so raw addresses never reach logs or
    the database. Exceeding the configured window/burst raises 429.

    Args:
        request: The incoming request whose client IP is used as the key.

    Raises:
        HTTPException: 429 when the rate limit is exceeded.
    """
    import hashlib

    settings = get_settings()
    client_ip = (request.client.host if request.client else "unknown").encode()
    ip_hash = hashlib.sha256(client_ip).hexdigest()[:16]
    key = f"rate:{ip_hash}"
    redis = _get_redis_client()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.rate_limit_window_seconds)
    if count > settings.rate_limit_max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
        )
