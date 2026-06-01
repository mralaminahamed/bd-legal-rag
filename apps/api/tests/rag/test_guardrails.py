"""Tests for normative-phrase guardrails scanner."""

from __future__ import annotations


def test_clean_text_returns_none() -> None:
    from app.rag.guardrails import scan

    result = scan("According to Section 103, workers are entitled to one day of rest.")
    assert result is None


def test_english_you_must_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("You must register your company within 30 days.")
    assert result is not None
    assert "you must" in result.lower()


def test_english_you_cannot_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("You cannot dismiss an employee without notice.")
    assert result is not None


def test_english_it_is_illegal_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("It is illegal to withhold wages.")
    assert result is not None


def test_english_you_are_required_to_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("You are required to maintain employee records.")
    assert result is not None


def test_bengali_must_phrase_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("আপনাকে অবশ্যই কোম্পানি নিবন্ধন করতে হবে।")
    assert result is not None


def test_bengali_cannot_phrase_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("আপনি পারবেন না কাউকে বরখাস্ত করতে।")
    assert result is not None


def test_bengali_illegal_phrase_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("এটি অবৈধ।")
    assert result is not None


def test_bengali_you_must_do_phrase_is_flagged() -> None:
    from app.rag.guardrails import scan

    result = scan("আপনাকে করতে হবে।")
    assert result is not None


def test_case_insensitive_en_detection() -> None:
    from app.rag.guardrails import scan

    result = scan("YOU MUST file a return annually.")
    assert result is not None


def test_returns_first_violation_found() -> None:
    from app.rag.guardrails import scan

    text = "You must do X. You cannot do Y. It is illegal to do Z."
    result = scan(text)
    assert result is not None
