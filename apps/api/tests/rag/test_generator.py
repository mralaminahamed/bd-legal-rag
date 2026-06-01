"""Generator pipeline acceptance tests (FR-GN-1..12, NFR-LS-1..5)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import Settings
from app.rag.retriever import RetrievedChunk
from app.rag.service import RetrievalResult

# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _settings(**overrides: Any) -> Settings:
    return Settings.model_validate(overrides)


def _chunk(
    chunk_id: str = "12345678-1234-1234-1234-123456789abc",
    content: str = "Every worker shall have one weekly holiday.",
    act_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    score: float = 0.90,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.UUID(chunk_id),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=uuid.UUID(act_id),
        hierarchy_path="Bangladesh Labour Act, 2006 > Chapter X > Section 103",
        content=content,
        language="en",
        score=score,
        rerank_score=score,
    )


def _retrieval_result(
    chunks: list[RetrievedChunk] | None = None,
    confidence: str = "HIGH",
    cross_lingual: bool = False,
    query: str = "What is the weekly holiday?",
) -> RetrievalResult:
    return RetrievalResult(
        query=query,
        detected_language="en",
        act_ids=[],
        cross_lingual=cross_lingual,
        chunks=chunks or [_chunk()],
        reranked=True,
        confidence=confidence,  # type: ignore[arg-type]
        as_of_date=date(2026, 1, 1),
    )


def _act_row() -> MagicMock:
    row = MagicMock()
    row.full_name_en = "Bangladesh Labour Act"
    row.full_name_bn = "বাংলাদেশ শ্রম আইন"
    row.act_year = 2006
    return row


@contextmanager
def _mock_provider(text: str) -> Generator[None, None, None]:
    from app.llm.base import CompletionResult, TokenUsage

    mock = MagicMock()
    mock.model = "claude-sonnet-4-6"
    mock.complete = AsyncMock(
        return_value=CompletionResult(text=text, usage=TokenUsage(10, 5), model="claude-sonnet-4-6")
    )
    with patch("app.llm.factory.create_provider", return_value=mock):
        yield


@contextmanager
def _mock_provider_unavailable() -> Generator[None, None, None]:
    from app.llm.base import ProviderUnavailable

    mock = MagicMock()
    mock.model = "claude-sonnet-4-6"
    mock.complete = AsyncMock(side_effect=ProviderUnavailable("down"))
    with patch("app.llm.factory.create_provider", return_value=mock):
        yield


@contextmanager
def _mock_cache_hit(text: str) -> Generator[None, None, None]:
    with patch("app.llm.cache.ResponseCache.get", new_callable=AsyncMock, return_value=text):
        yield


def _mock_act_query(mock_session: Any) -> Any:
    """Context manager: mock the DB query that resolves act metadata."""

    @contextmanager
    def _ctx() -> Generator[None, None, None]:
        row = _act_row()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [row]
        # Simulate act row having id field
        row.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        mock_session.execute = AsyncMock(return_value=result_mock)
        yield

    return _ctx()


@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock()


# ─── Type shape tests ──────────────────────────────────────────────────────────

def test_stream_event_has_required_fields() -> None:
    from app.rag.generator import StreamEvent

    ev = StreamEvent(
        type="token",
        text="hello",
        answer=None,
        citations=None,
        disclaimer=None,
        cached=False,
        degraded=False,
        declined=False,
        usage=None,
    )
    assert ev.type == "token"
    assert ev.text == "hello"


def test_generate_response_has_required_fields() -> None:
    from app.rag.generator import GenerateResponse

    resp = GenerateResponse(
        answer="The answer.",
        citations=[],
        disclaimer="disclaimer text",
        cached=False,
        degraded=False,
        declined=False,
        usage=None,
        disclaimer_version="v1",
    )
    assert resp.answer == "The answer."
    assert resp.disclaimer_version == "v1"


# ─── Disclaimer present on every path (NFR-LS-1) ─────────────────────────────

@pytest.mark.asyncio
async def test_disclaimer_present_on_normal_response_NFR_LS_1(
    mock_db_session: Any,
) -> None:
    from app.rag.generator import generate

    with _mock_provider("The section provides for one weekly holiday."), \
         _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        )

    assert resp.disclaimer
    assert len(resp.disclaimer) > 20
    assert resp.disclaimer in resp.answer


@pytest.mark.asyncio
async def test_disclaimer_present_on_decline_response_NFR_LS_1(
    mock_db_session: Any,
) -> None:
    from app.rag.generator import generate

    result = _retrieval_result(query="Should I sign this contract?")
    resp = await generate(
        retrieval_result=result,
        session=mock_db_session,
        settings=_settings(),
    )
    assert resp.declined is True
    assert resp.disclaimer in resp.answer


@pytest.mark.asyncio
async def test_disclaimer_present_on_failopen_response_NFR_LS_1(
    mock_db_session: Any,
) -> None:
    from app.rag.generator import generate

    with _mock_provider_unavailable(), _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        )

    assert resp.degraded is True
    assert resp.disclaimer in resp.answer


@pytest.mark.asyncio
async def test_disclaimer_present_on_cache_hit_NFR_LS_1(
    mock_db_session: Any,
) -> None:
    from app.rag.generator import generate

    with _mock_cache_hit("Cached answer without disclaimer"), \
         _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        )

    assert resp.cached is True
    assert resp.disclaimer in resp.answer


# ─── Decline gate ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_advice_seeking_en_declines_NFR_LS_3(mock_db_session: Any) -> None:
    from app.rag.generator import generate

    result = _retrieval_result(query="Should I register my company?")
    resp = await generate(retrieval_result=result, session=mock_db_session, settings=_settings())
    assert resp.declined is True


@pytest.mark.asyncio
async def test_advice_seeking_bn_declines_NFR_LS_3(mock_db_session: Any) -> None:
    from app.rag.generator import generate

    result = _retrieval_result(query="আমার কি করা উচিত?")
    resp = await generate(retrieval_result=result, session=mock_db_session, settings=_settings())
    assert resp.declined is True


# ─── Citation validator strips fabricated placeholders ────────────────────────

@pytest.mark.asyncio
async def test_citation_validator_strips_fabricated_placeholder_ADR_005(
    mock_db_session: Any,
) -> None:
    from app.rag.generator import generate

    with _mock_provider("Per {{cite:12345678-1234-1234-1234-123456789abc}} workers get rest. "
                        "Also {{cite:00000000-0000-0000-0000-000000000000}} says something."), \
         _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        )

    assert "00000000-0000-0000-0000-000000000000" not in resp.answer
    assert "{{cite:" not in resp.answer


# ─── Guardrails ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guardrails_retry_on_first_violation(mock_db_session: Any) -> None:
    from app.rag.generator import generate

    call_count = 0

    async def provider_complete(req: Any) -> Any:
        nonlocal call_count
        from app.llm.base import CompletionResult, TokenUsage
        call_count += 1
        if call_count == 1:
            return CompletionResult(
                text="You must register within 30 days.",
                usage=TokenUsage(10, 5),
                model="claude-sonnet-4-6",
            )
        cited = "{{cite:12345678-1234-1234-1234-123456789abc}}"
        return CompletionResult(
            text=f"According to {cited}, registration is required.",
            usage=TokenUsage(10, 5),
            model="claude-sonnet-4-6",
        )

    mock_provider = MagicMock()
    mock_provider.model = "claude-sonnet-4-6"
    mock_provider.complete = provider_complete

    with patch("app.llm.factory.create_provider", return_value=mock_provider), \
         _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        )

    assert call_count == 2
    assert resp.degraded is False
    assert "you must" not in resp.answer.lower()


@pytest.mark.asyncio
async def test_guardrails_fail_open_on_second_violation(mock_db_session: Any) -> None:
    from app.rag.generator import generate

    async def always_violates(req: Any) -> Any:
        from app.llm.base import CompletionResult, TokenUsage
        return CompletionResult(
            text="You must comply with all regulations.",
            usage=TokenUsage(10, 5),
            model="claude-sonnet-4-6",
        )

    mock_provider = MagicMock()
    mock_provider.model = "claude-sonnet-4-6"
    mock_provider.complete = always_violates

    with patch("app.llm.factory.create_provider", return_value=mock_provider), \
         _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        )

    assert resp.degraded is True


# ─── Circuit breaker ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_circuit_breaker_refuses_oversized_request(mock_db_session: Any) -> None:
    from app.rag.generator import generate

    s = _settings(cost_ceiling_usd_per_request=0.000001)
    with _mock_act_query(mock_db_session):
        resp = await generate(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=s,
        )

    assert resp.degraded is True


# ─── Streaming ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_yields_token_events_then_final(mock_db_session: Any) -> None:
    from app.rag.generator import StreamEvent, generate_stream

    tokens = ["According ", "to the law, ", "workers get rest."]

    async def fake_stream(req: Any):  # type: ignore[no-untyped-def]
        for t in tokens:
            yield t

    mock_provider = MagicMock()
    mock_provider.model = "claude-sonnet-4-6"
    mock_provider.stream = fake_stream

    with patch("app.llm.factory.create_provider", return_value=mock_provider), \
         _mock_act_query(mock_db_session):
        events: list[StreamEvent] = []
        async for ev in generate_stream(
            retrieval_result=_retrieval_result(),
            session=mock_db_session,
            settings=_settings(),
        ):
            events.append(ev)

    token_events = [e for e in events if e.type == "token"]
    final_events = [e for e in events if e.type == "final"]

    assert len(token_events) == len(tokens)
    assert len(final_events) == 1
    final = final_events[0]
    assert final.answer is not None
    assert final.disclaimer is not None
    assert final.disclaimer in final.answer
