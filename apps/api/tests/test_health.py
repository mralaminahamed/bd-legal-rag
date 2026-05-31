"""Tests for the application factory and the /health endpoint.

Dependency probes are patched here so these unit tests stay free of a live
database or Redis. Real connectivity is covered by test_db_integration.
"""

from __future__ import annotations

import pytest
from app import main
from fastapi.testclient import TestClient


@pytest.fixture
def healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force both dependency probes to report reachable."""

    async def _ok() -> bool:
        return True

    monkeypatch.setattr(main, "_check_database", _ok)
    monkeypatch.setattr(main, "_check_redis", _ok)


def test_health_ok_when_dependencies_reachable(healthy: None) -> None:
    """/health returns 200 and reports every dependency ok."""
    client = TestClient(main.create_app())
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["service"]
    assert body["environment"]


def test_health_degraded_when_database_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """/health returns 503 and flags the database when it is unreachable."""

    async def _ok() -> bool:
        return True

    async def _down() -> bool:
        return False

    monkeypatch.setattr(main, "_check_database", _down)
    monkeypatch.setattr(main, "_check_redis", _ok)

    client = TestClient(main.create_app())
    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert body["redis"] == "ok"


def test_health_degraded_when_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """/health returns 503 and flags redis when it is unreachable."""

    async def _ok() -> bool:
        return True

    async def _down() -> bool:
        return False

    monkeypatch.setattr(main, "_check_database", _ok)
    monkeypatch.setattr(main, "_check_redis", _down)

    client = TestClient(main.create_app())
    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["redis"] == "unavailable"
    assert body["database"] == "ok"


def test_health_sets_correlation_id_header(healthy: None) -> None:
    """Every response carries a correlation id for tracing."""
    client = TestClient(main.create_app())
    response = client.get("/health")

    assert response.headers.get("X-Correlation-ID")


def test_inbound_correlation_id_is_echoed(healthy: None) -> None:
    """A caller-supplied correlation id is threaded back unchanged."""
    client = TestClient(main.create_app())
    response = client.get("/health", headers={"X-Correlation-ID": "trace-abc-123"})

    assert response.headers["X-Correlation-ID"] == "trace-abc-123"


def test_service_name_in_health_response(healthy: None) -> None:
    """The health response carries the configured service name."""
    client = TestClient(main.create_app())
    body = client.get("/health").json()

    assert body["service"] == "bd-legal-rag"
