"""Tests for query and feedback endpoints (FR-DL-1..3, FR-FB-1..2)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.generator import GenerateResponse
from app.rag.retriever import RetrievedChunk
from app.rag.service import RetrievalResult
from fastapi.testclient import TestClient
from sqlalchemy.engine import Result


def _make_retrieval(query: str = "What is section 103?") -> RetrievalResult:
    chunk = RetrievedChunk(
        chunk_id=uuid.UUID("12345678-1234-1234-1234-123456789abc"),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        hierarchy_path="Bangladesh Labour Act, 2006 > Section 103",
        content="Every worker shall have one weekly holiday.",
        language="en",
        score=0.9,
        rerank_score=0.9,
    )
    return RetrievalResult(
        query=query,
        detected_language="en",
        act_ids=[],
        cross_lingual=False,
        chunks=[chunk],
        reranked=True,
        confidence="HIGH",
        as_of_date=date.today(),
    )


def _make_gen(declined: bool = False, cached: bool = False) -> GenerateResponse:
    return GenerateResponse(
        answer="Section 103 provides for weekly holiday.\n\n---\nFor information only.",
        citations=["12345678-1234-1234-1234-123456789abc"],
        disclaimer="For information only.",
        cached=cached,
        degraded=False,
        declined=declined,
        usage=None,
        disclaimer_version="v1",
    )


def _empty_scalars() -> MagicMock:
    """Return a mock execute result that yields an empty scalar list."""
    result = MagicMock(spec=Result)
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    return result


def _make_fake_query_record() -> MagicMock:
    """Return a mock Query ORM record with a stable id."""
    record = MagicMock()
    record.id = uuid.uuid4()
    return record


def _make_app_with_db_override(
    session_mock: Any,
) -> Any:
    """Create the app with a DB session dependency override."""
    from app.api.deps import get_db, rate_limit
    from app.main import create_app

    app = create_app()

    async def _override_db() -> Any:
        yield session_mock

    async def _override_rate_limit() -> None:
        return None

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[rate_limit] = _override_rate_limit
    return app


def _make_empty_session() -> MagicMock:
    """Return a session mock where every lookup returns None/empty."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_empty_scalars())
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_logging_session() -> MagicMock:
    """Return a session mock that materialises a Query id on refresh."""
    record = _make_fake_query_record()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_empty_scalars())
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(obj: Any) -> None:
        obj.id = record.id

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


# ── Query endpoint ──────────────────────────────────────────────────────────

def test_query_returns_200_with_disclaimer() -> None:
    """POST /api/v1/query returns 200 with disclaimer embedded in answer (NFR-LS-1)."""
    retrieval = _make_retrieval()
    gen = _make_gen()

    app = _make_app_with_db_override(_make_logging_session())
    with (
        patch("app.api.routes_query.retrieve", new=AsyncMock(return_value=retrieval)),
        patch("app.api.routes_query.generate", new=AsyncMock(return_value=gen)),
    ):
        client = TestClient(app)
        resp = client.post("/api/v1/query", json={"question": "What is section 103?"})

    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert "disclaimer" in body
    assert "query_id" in body
    assert body["disclaimer"] in body["answer"]


def test_query_declined_response_has_disclaimer_NFR_LS_1() -> None:
    """Declined query still carries the disclaimer (NFR-LS-1)."""
    retrieval = _make_retrieval(query="Should I sign this contract?")
    gen = _make_gen(declined=True)
    gen.answer = "Cannot answer.\n\nFor information only."

    app = _make_app_with_db_override(_make_logging_session())
    with (
        patch("app.api.routes_query.retrieve", new=AsyncMock(return_value=retrieval)),
        patch("app.api.routes_query.generate", new=AsyncMock(return_value=gen)),
    ):
        client = TestClient(app)
        resp = client.post("/api/v1/query", json={"question": "Should I sign this contract?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["declined"] is True
    assert body["disclaimer"] in body["answer"]


def test_query_rejects_empty_question() -> None:
    """POST /api/v1/query returns 422 for empty question string."""
    from app.main import create_app
    client = TestClient(create_app())
    resp = client.post("/api/v1/query", json={"question": ""})
    assert resp.status_code == 422


def test_query_rejects_invalid_language() -> None:
    """POST /api/v1/query returns 422 for unknown language value."""
    from app.main import create_app
    client = TestClient(create_app())
    resp = client.post("/api/v1/query", json={"question": "hello", "language": "fr"})
    assert resp.status_code == 422


def test_query_unknown_act_slug_returns_404() -> None:
    """POST /api/v1/query returns 404 for unknown act_slug (empty DB)."""
    app = _make_app_with_db_override(_make_empty_session())
    client = TestClient(app)
    resp = client.post(
        "/api/v1/query",
        json={"question": "What is section 1?", "act_slug": "nonexistent-act-xyz"},
    )
    assert resp.status_code == 404


# ── Stream endpoint ─────────────────────────────────────────────────────────

def test_stream_returns_sse_content_type() -> None:
    """POST /api/v1/query/stream returns text/event-stream."""
    from app.rag.generator import StreamEvent

    retrieval = _make_retrieval()

    async def fake_stream(**kwargs: Any) -> Any:
        yield StreamEvent(
            type="token", text="Hello ", answer=None, citations=None,
            disclaimer=None, cached=False, degraded=False, declined=False, usage=None,
        )
        yield StreamEvent(
            type="final", text="", answer="Hello world.\n\nFor info only.",
            citations=[], disclaimer="For info only.",
            cached=False, degraded=False, declined=False, usage=None,
        )

    app = _make_app_with_db_override(_make_logging_session())
    with (
        patch("app.api.routes_query.retrieve", new=AsyncMock(return_value=retrieval)),
        patch("app.api.routes_query.generate_stream", side_effect=fake_stream),
    ):
        client = TestClient(app)
        resp = client.post("/api/v1/query/stream", json={"question": "hello"})

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    lines = [line for line in resp.text.split("\n") if line.startswith("data:")]
    assert len(lines) >= 1  # at least the final event


# ── Feedback endpoint ───────────────────────────────────────────────────────

def test_feedback_returns_422_for_non_uuid_query_id() -> None:
    """POST /api/v1/feedback returns 422 when query_id is not a UUID."""
    app = _make_app_with_db_override(_make_empty_session())
    client = TestClient(app)
    resp = client.post(
        "/api/v1/feedback",
        json={"query_id": "not-a-uuid", "rating": "helpful"},
    )
    assert resp.status_code == 422


def test_feedback_returns_404_for_missing_query() -> None:
    """POST /api/v1/feedback returns 404 when query_id doesn't exist in DB."""
    app = _make_app_with_db_override(_make_empty_session())
    client = TestClient(app)
    resp = client.post(
        "/api/v1/feedback",
        json={"query_id": str(uuid.uuid4()), "rating": "helpful"},
    )
    assert resp.status_code == 404


def test_feedback_rejects_invalid_rating() -> None:
    """POST /api/v1/feedback returns 422 for unknown rating value."""
    from app.main import create_app
    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/feedback",
        json={"query_id": str(uuid.uuid4()), "rating": "love_it"},
    )
    assert resp.status_code == 422
