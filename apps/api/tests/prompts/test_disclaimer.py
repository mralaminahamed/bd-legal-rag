"""Tests for versioned disclaimer (NFR-LS-1)."""

from __future__ import annotations

import pytest
from app.prompts.safety.disclaimer import Disclaimer, inject, resolve


def test_resolve_v1_returns_disclaimer() -> None:
    d = resolve("v1")
    assert isinstance(d, Disclaimer)
    assert d.version == "v1"
    assert len(d.en) > 20
    assert len(d.bn) > 20


def test_resolve_unknown_version_raises() -> None:
    with pytest.raises(KeyError, match="unknown disclaimer version"):
        resolve("v99")


def test_inject_appends_english_disclaimer() -> None:
    result = inject("The section says X.", version="v1", language="en")
    d = resolve("v1")
    assert result.endswith(d.en)
    assert "The section says X." in result


def test_inject_appends_bengali_disclaimer() -> None:
    result = inject("ধারাটি বলে X।", version="v1", language="bn")
    d = resolve("v1")
    assert result.endswith(d.bn)


def test_inject_on_empty_response_still_appends() -> None:
    result = inject("", version="v1", language="en")
    d = resolve("v1")
    assert d.en in result


def test_inject_adds_separator() -> None:
    result = inject("answer", version="v1", language="en")
    assert "\n\n" in result
