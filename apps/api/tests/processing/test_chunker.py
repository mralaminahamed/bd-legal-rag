"""Unit tests for the section-hierarchy-aware chunker (FR-PR-1, FR-PR-2)."""

from __future__ import annotations

import pytest
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Settings with tight token limits to exercise splitting."""
    return Settings(
        chunk_target_tokens=10,
        chunk_max_tokens=20,
        chunk_overlap_tokens=3,
    )


@pytest.fixture
def default_settings() -> Settings:
    """Default settings (chunk_max_tokens=768)."""
    return Settings()


def test_count_tokens_nonempty() -> None:
    from app.processing.chunker import _count_tokens

    assert _count_tokens("hello world") >= 1


def test_count_tokens_empty_returns_one() -> None:
    from app.processing.chunker import _count_tokens

    assert _count_tokens("") == 1


def test_count_tokens_longer_text_returns_more() -> None:
    from app.processing.chunker import _count_tokens

    short = _count_tokens("hi")
    long = _count_tokens("a" * 400)
    assert long > short


def test_single_chunk_for_short_provision(default_settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    text = "Every worker shall be given at least one day off per week."
    path = "Bangladesh Labour Act, 2006 > Chapter X > Section 103 (Weekly holiday)"
    specs = chunk_provision(text, path, default_settings)
    assert len(specs) == 1
    assert specs[0].chunk_index == 0
    assert specs[0].hierarchy_path == path
    assert path in specs[0].content
    assert text in specs[0].content


def test_hierarchy_path_prepended_to_content(default_settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    text = "Sample provision text."
    path = "Test Act, 2006 > Section 1"
    specs = chunk_provision(text, path, default_settings)
    assert len(specs) == 1
    assert specs[0].content.startswith(path)


def test_empty_text_returns_no_chunks(default_settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    specs = chunk_provision("", "Some Act > Section 1", default_settings)
    assert specs == []


def test_whitespace_only_returns_no_chunks(default_settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    specs = chunk_provision("   \n\n  ", "Some Act > Section 1", default_settings)
    assert specs == []


def test_token_count_stored_on_spec(default_settings: Settings) -> None:
    from app.processing.chunker import _count_tokens, chunk_provision

    text = "Short provision."
    path = "Test Act > Section 1"
    specs = chunk_provision(text, path, default_settings)
    assert specs[0].token_count == _count_tokens(specs[0].content)


def test_oversized_provision_splits_into_multiple_chunks(settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    para_a = "A" * 100
    para_b = "B" * 100
    text = f"{para_a}\n\n{para_b}"
    specs = chunk_provision(text, "Act > Section 1", settings)
    assert len(specs) >= 2
    for idx, spec in enumerate(specs):
        assert spec.chunk_index == idx


def test_split_chunks_all_have_hierarchy_path(settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    path = "My Act, 2006 > Chapter I > Section 5"
    text = ("word " * 30 + "\n\n") * 3
    specs = chunk_provision(text, path, settings)
    assert all(spec.hierarchy_path == path for spec in specs)
    assert all(spec.content.startswith(path) for spec in specs)


def test_bengali_text_preserved(default_settings: Settings) -> None:
    from app.processing.chunker import chunk_provision

    bn_text = "প্রত্যেক শ্রমিক প্রতি সপ্তাহে এক দিন পূর্ণ বেতনে ছুটি পাওয়ার অধিকারী।"
    path = "বাংলাদেশ শ্রম আইন, ২০০৬ > অধ্যায় X > ধারা ১০৩"
    specs = chunk_provision(bn_text, path, default_settings)
    assert len(specs) == 1
    assert bn_text in specs[0].content
    assert path in specs[0].content
