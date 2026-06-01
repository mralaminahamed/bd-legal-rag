"""Tests for browse endpoints (FR-FB-3..5, FR-DL-3)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.engine import Result


def _empty_scalars() -> MagicMock:
    """Return a mock execute result that yields an empty scalar list."""
    result = MagicMock(spec=Result)
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    return result


def _make_app_with_db_override() -> Any:
    """Create the app with an empty-DB session dependency override."""
    from app.api.deps import get_db
    from app.main import create_app

    app = create_app()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_empty_scalars())
    session.get = AsyncMock(return_value=None)

    async def _override_db() -> Any:
        yield session

    app.dependency_overrides[get_db] = _override_db
    return app


def test_list_acts_returns_200() -> None:
    """GET /api/v1/acts returns 200 (empty DB = empty list)."""
    client = TestClient(_make_app_with_db_override())
    resp = client.get("/api/v1/acts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_act_structure_unknown_slug_returns_404() -> None:
    """GET /api/v1/acts/{slug}/structure returns 404 for unknown slug."""
    client = TestClient(_make_app_with_db_override())
    resp = client.get("/api/v1/acts/definitely-not-an-act/structure")
    assert resp.status_code == 404


def test_section_detail_unknown_act_returns_404() -> None:
    """GET /api/v1/acts/{slug}/sections/{section} returns 404 for unknown act."""
    client = TestClient(_make_app_with_db_override())
    resp = client.get("/api/v1/acts/definitely-not-an-act/sections/103")
    assert resp.status_code == 404
