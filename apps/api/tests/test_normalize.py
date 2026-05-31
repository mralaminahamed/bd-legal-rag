"""Tests for provision text normalisation.

Verifies that Bengali characters pass through bit-for-bit and that executable
markup is stripped correctly (NFR-SC-4).
"""

from __future__ import annotations

from app.ingestion.normalize import clean_provision_text, extract_text

_BENGALI_TEXT = "বাংলাদেশ শ্রম আইন, ২০০৬"
_COMBINING_HEAVY = "ক্ষ"  # ক + ্ + ষ — combining sequence


def test_bengali_text_preserved_bit_for_bit() -> None:
    """Bengali characters survive extract_text unchanged."""
    html = f"<p>{_BENGALI_TEXT}</p>"
    result = extract_text(html)
    assert _BENGALI_TEXT in result


def test_bengali_combining_marks_preserved() -> None:
    """Combining sequences (conjuncts) are not altered."""
    html = f"<p>{_COMBINING_HEAVY}</p>"
    result = extract_text(html)
    assert _COMBINING_HEAVY in result
    # Verify the sequence is exactly the same bytes.
    assert result.strip() == _COMBINING_HEAVY


def test_script_tags_stripped() -> None:
    """<script> elements and their content are stripped."""
    html = "<p>Provision text.</p><script>alert('xss')</script>"
    result = extract_text(html)
    assert "alert" not in result
    assert "Provision text." in result


def test_style_tags_stripped() -> None:
    """<style> elements are stripped."""
    html = "<p>Body text.</p><style>body { color: red; }</style>"
    result = extract_text(html)
    assert "color" not in result
    assert "Body text." in result


def test_no_nfkc_normalization() -> None:
    """NFKC normalization is NOT applied — characters must survive unchanged."""
    # U+2026 HORIZONTAL ELLIPSIS — NFKC would keep it but check exact bytes survive
    special = "…"
    html = f"<p>Section 1{special}</p>"
    result = extract_text(html)
    assert special in result


def test_excess_whitespace_collapsed() -> None:
    """Multiple spaces and blank lines are collapsed to single separators."""
    html = "<p>Section    1</p><p></p><p>    </p><p>Body  text.</p>"
    result = extract_text(html)
    assert "Section 1" in result
    assert "Body text." in result
    assert "   " not in result


def test_clean_provision_text_trims_and_collapses() -> None:
    """clean_provision_text collapses whitespace without touching Unicode."""
    text = "  বাংলাদেশ   শ্রম   আইন  "
    result = clean_provision_text(text)
    assert result == "বাংলাদেশ শ্রম আইন"


def test_empty_html_returns_empty_string() -> None:
    """Empty or markup-only HTML returns an empty string."""
    assert extract_text("") == ""
    assert extract_text("<p></p>") == ""
    assert extract_text("<div>   </div>") == ""
