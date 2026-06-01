"""Tests for bilingual decline gate (NFR-LS-3, FR-GN-3)."""

from __future__ import annotations

import uuid

from app.config import Settings
from app.rag.retriever import RetrievedChunk


def _settings() -> Settings:
    return Settings.model_validate({})


def _chunk(score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        revision_id=uuid.uuid4(),
        provision_id=uuid.uuid4(),
        act_id=uuid.uuid4(),
        hierarchy_path="Act > Section 1",
        content="text",
        language="en",
        score=score,
        rerank_score=score,
    )


def test_english_should_i_declines() -> None:
    from app.rag.decline_gate import classify

    decision = classify("Should I sign this contract?", chunks=[_chunk()], settings=_settings())
    assert decision.declined is True
    assert decision.reason


def test_english_what_should_i_do_declines() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "What should I do if my employer doesn't pay me?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is True


def test_english_is_it_legal_for_me_declines() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "Is it legal for me to dismiss an employee without notice?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is True


def test_english_can_i_sue_declines() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "Can I sue my employer for wrongful termination?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is True


def test_bengali_advice_seeking_declines() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "আমার কি করা উচিত যদি আমার নিয়োগকর্তা আমাকে বেতন না দেন?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is True


def test_bengali_can_i_declines() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "আমি কি মামলা করতে পারি?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is True


def test_factual_query_does_not_decline() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "What is the weekly holiday entitlement under the Labour Act?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is False


def test_bengali_factual_query_does_not_decline() -> None:
    from app.rag.decline_gate import classify

    decision = classify(
        "শ্রম আইন অনুযায়ী সাপ্তাহিক ছুটি কত দিন?",
        chunks=[_chunk()],
        settings=_settings(),
    )
    assert decision.declined is False


def test_decline_fires_even_when_relevant_chunks_returned() -> None:
    """NFR-LS-3: decline path runs even with relevant chunks."""
    from app.rag.decline_gate import classify

    # High-scoring chunks, but query is advice-seeking
    chunks = [_chunk(0.95), _chunk(0.92)]
    decision = classify(
        "Should I register my company?",
        chunks=chunks,
        settings=_settings(),
    )
    assert decision.declined is True


def test_low_recall_triggers_decline() -> None:
    """Empty retrieval below the recall floor triggers decline."""
    from app.rag.decline_gate import classify

    decision = classify(
        "What does Section 200 say?",
        chunks=[],  # zero recall
        settings=_settings(),
    )
    assert decision.declined is True
    assert "recall" in decision.reason.lower()
