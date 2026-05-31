"""Tests for application configuration validation (NFR-MN-4)."""

from __future__ import annotations

import pytest
from app.config import Settings


def test_default_settings_are_valid() -> None:
    """Settings build cleanly with no environment overrides."""
    settings = Settings()
    assert settings.app_name == "bd-legal-rag"
    assert settings.embed_model == "embed-multilingual-v3.0"
    assert settings.embed_dimensions == 1024
    assert settings.rerank_model == "rerank-multilingual-v3.0"
    assert settings.active_disclaimer_version == "v1"
    assert settings.active_decline_version == "v1"


def test_chunk_max_must_be_gte_target() -> None:
    """chunk_max_tokens < chunk_target_tokens is rejected."""
    with pytest.raises(ValueError, match="chunk_max_tokens"):
        Settings(chunk_target_tokens=768, chunk_max_tokens=512)


def test_chunk_overlap_must_be_lt_target() -> None:
    """chunk_overlap_tokens >= chunk_target_tokens is rejected."""
    with pytest.raises(ValueError, match="chunk_overlap_tokens"):
        Settings(chunk_target_tokens=512, chunk_overlap_tokens=512)


def test_top_k_must_be_lte_top_n() -> None:
    """retrieval_top_k > retrieval_top_n is rejected."""
    with pytest.raises(ValueError, match="retrieval_top_k"):
        Settings(retrieval_top_n=8, retrieval_top_k=10)


def test_both_retrieval_weights_zero_rejected() -> None:
    """Both vector and lexical weights set to zero is rejected."""
    with pytest.raises(ValueError, match="vector_weight"):
        Settings(vector_weight=0.0, lexical_weight=0.0)


def test_confidence_thresholds_ordered() -> None:
    """t_medium > t_high is rejected."""
    with pytest.raises(ValueError, match="confidence_t_medium"):
        Settings(confidence_t_high=0.5, confidence_t_medium=0.8)


def test_bdrag_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """BDRAG_ environment prefix is respected."""
    monkeypatch.setenv("BDRAG_LOG_LEVEL", "DEBUG")
    settings = Settings()
    assert settings.log_level == "DEBUG"
