"""Tests for admin endpoints (NFR-SC-2, FR-FB-3, FR-DL-4)."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Result


def _empty_scalars() -> MagicMock:
    """Return a mock execute result that yields an empty scalar list."""
    result = MagicMock(spec=Result)
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    result.fetchone.return_value = None
    result.scalar.return_value = 0
    return result


def _make_app_with_token(token: str = "test-secret") -> tuple[Any, str]:
    from app.config import get_settings
    os.environ["BDRAG_ADMIN_BEARER_TOKEN"] = token
    get_settings.cache_clear()
    from app.api.deps import get_db, get_redis
    from app.main import create_app

    app = create_app()

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_empty_scalars())
    session.get = AsyncMock(return_value=None)

    async def _override_db() -> Any:
        yield session

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)

    async def _override_redis() -> Any:
        return redis_mock

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis
    return app, token


def _make_app_no_token() -> Any:
    from app.config import get_settings
    os.environ.pop("BDRAG_ADMIN_BEARER_TOKEN", None)
    get_settings.cache_clear()
    from app.main import create_app
    return create_app()


# ── Auth enforcement ────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,method", [
    ("/api/v1/admin/acts", "GET"),
    ("/api/v1/admin/acts/ingest", "POST"),
    ("/api/v1/admin/llm", "GET"),
    ("/api/v1/admin/llm", "PUT"),
    ("/api/v1/admin/llm", "DELETE"),
    ("/api/v1/admin/metrics", "GET"),
    ("/api/v1/admin/queries", "GET"),
])
def test_admin_rejects_unauthenticated(path: str, method: str) -> None:
    """Admin endpoints return 401 without bearer token (NFR-SC-2)."""
    app = _make_app_no_token()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.request(method, path, json={})
    assert resp.status_code == 401, f"Expected 401 for {method} {path}, got {resp.status_code}"


def test_admin_rejects_wrong_token() -> None:
    """Admin endpoint returns 401 with wrong bearer token."""
    app, _ = _make_app_with_token("correct-token")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(
        "/api/v1/admin/acts",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


# ── With valid auth ─────────────────────────────────────────────────────────

def test_admin_acts_returns_list_with_auth() -> None:
    """GET /api/v1/admin/acts returns 200 with valid token (mocked DB)."""
    app, token = _make_app_with_token()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(
        "/api/v1/admin/acts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_admin_llm_get_returns_schema() -> None:
    """GET /api/v1/admin/llm returns correct schema shape (mocked Redis)."""

    app, token = _make_app_with_token()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(
        "/api/v1/admin/llm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "provider" in body
    assert "model" in body
    assert "source" in body
    assert body["source"] in ("env", "override")


def test_admin_llm_put_rejects_invalid_provider() -> None:
    """PUT /api/v1/admin/llm returns 422 for unknown provider."""
    app, token = _make_app_with_token()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.put(
        "/api/v1/admin/llm",
        json={"provider": "cohere", "model": "command-r"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_admin_metrics_returns_schema() -> None:
    """GET /api/v1/admin/metrics returns correct schema shape (mocked DB)."""
    app, token = _make_app_with_token()

    # metrics uses raw SQL; mock the row object
    mock_row = MagicMock()
    mock_row.total = 0
    mock_row.declined_count = 0
    mock_row.high_count = 0
    mock_row.medium_count = 0
    mock_row.low_count = 0
    mock_row.cached_count = 0
    mock_row.degraded_count = 0
    mock_row.p95_latency = None
    mock_row.daily_spend = 0

    window_result = MagicMock()
    window_result.fetchone.return_value = mock_row

    fb_result = MagicMock()
    fb_result.scalar.return_value = 0

    # Override execute to return window_result for the first call, fb_result for the second
    call_count: list[int] = [0]

    async def _side_execute(*args: Any, **kwargs: Any) -> Any:
        call_count[0] += 1
        if call_count[0] == 1:
            return window_result
        return fb_result

    # Rebuild app with a custom session mock for metrics
    from app.api.deps import get_db, get_redis
    from app.main import create_app

    metrics_app = create_app()
    os.environ["BDRAG_ADMIN_BEARER_TOKEN"] = token
    from app.config import get_settings
    get_settings.cache_clear()
    metrics_app = create_app()

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=_side_execute)

    async def _override_db() -> Any:
        yield session

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)

    async def _override_redis() -> Any:
        return redis_mock

    metrics_app.dependency_overrides[get_db] = _override_db
    metrics_app.dependency_overrides[get_redis] = _override_redis

    client = TestClient(metrics_app, raise_server_exceptions=False)
    resp = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total_queries" in body
    assert "decline_rate" in body
    assert "confidence_breakdown" in body
    assert all(k in body["confidence_breakdown"] for k in ("HIGH", "MEDIUM", "LOW"))


def test_admin_queries_returns_schema() -> None:
    """GET /api/v1/admin/queries returns correct schema shape (mocked DB)."""
    from app.api.deps import get_db, get_redis
    from app.main import create_app

    token = "test-secret-queries"
    os.environ["BDRAG_ADMIN_BEARER_TOKEN"] = token
    from app.config import get_settings
    get_settings.cache_clear()
    app = create_app()

    rows_result = MagicMock(spec=Result)
    rows_result.scalars.return_value.all.return_value = []

    count_result = MagicMock(spec=Result)
    count_result.scalar.return_value = 0

    call_count: list[int] = [0]

    async def _side_execute(*args: Any, **kwargs: Any) -> Any:
        call_count[0] += 1
        if call_count[0] == 1:
            return rows_result
        return count_result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=_side_execute)

    async def _override_db() -> Any:
        yield session

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)

    async def _override_redis() -> Any:
        return redis_mock

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(
        "/api/v1/admin/queries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "queries" in body
    assert "total" in body
    assert isinstance(body["queries"], list)


def test_admin_ingest_unknown_slug_returns_404() -> None:
    """POST /api/v1/admin/acts/{slug}/ingest returns 404 for unknown slug."""
    app, token = _make_app_with_token()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/admin/acts/nonexistent-act-xyz/ingest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
