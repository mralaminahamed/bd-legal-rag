"""Tests for citation formatter and placeholder resolver (ADR-005)."""

from __future__ import annotations


def test_format_citation_english() -> None:
    from app.rag.citation import CitationContext, format_citation

    ctx = CitationContext(
        chunk_id="abc-123",
        act_name_en="Bangladesh Labour Act",
        act_name_bn="বাংলাদেশ শ্রম আইন",
        act_year=2006,
        section_ref="103(1)(a)",
    )
    result = format_citation(ctx, language="en")
    assert result == "Section 103(1)(a) of Bangladesh Labour Act, 2006"


def test_format_citation_bengali_uses_bengali_numerals() -> None:
    from app.rag.citation import CitationContext, format_citation

    ctx = CitationContext(
        chunk_id="abc-123",
        act_name_en="Bangladesh Labour Act",
        act_name_bn="বাংলাদেশ শ্রম আইন",
        act_year=2006,
        section_ref="103(1)(a)",
    )
    result = format_citation(ctx, language="bn")
    # Year 2006 → ২০০৬; section 103 → ১০৩
    assert "২০০৬" in result
    assert "১০৩" in result
    assert "বাংলাদেশ শ্রম আইন" in result


def test_format_citation_bengali_form() -> None:
    from app.rag.citation import CitationContext, format_citation

    ctx = CitationContext(
        chunk_id="abc-123",
        act_name_en="Income Tax Act",
        act_name_bn="আয়কর আইন",
        act_year=2023,
        section_ref="50",
    )
    result = format_citation(ctx, language="bn")
    assert "আয়কর আইন" in result
    assert "২০২৩" in result
    assert "ধারা" in result
    assert "৫০" in result


def test_to_bn_numerals() -> None:
    from app.rag.citation import to_bn_numerals

    assert to_bn_numerals("2006") == "২০০৬"
    assert to_bn_numerals("103(1)(a)") == "১০৩(১)(a)"  # letters preserved


def test_resolve_placeholders_substitutes_known_ids() -> None:
    from app.rag.citation import CitationContext, resolve_placeholders

    ctx = CitationContext(
        chunk_id="abc-123",
        act_name_en="Bangladesh Labour Act",
        act_name_bn="বাংলাদেশ শ্রম আইন",
        act_year=2006,
        section_ref="103",
    )
    text = "Per {{cite:abc-123}}, workers have rights."
    result = resolve_placeholders(text, contexts={"abc-123": ctx}, language="en")
    assert "{{cite:abc-123}}" not in result
    assert "Section 103 of Bangladesh Labour Act, 2006" in result


def test_resolve_placeholders_strips_unknown_ids() -> None:
    from app.rag.citation import CitationContext, resolve_placeholders

    ctx = CitationContext(
        chunk_id="known-id",
        act_name_en="Act",
        act_name_bn="আইন",
        act_year=2020,
        section_ref="1",
    )
    text = "Per {{cite:known-id}} and {{cite:fabricated-id}}, the law says..."
    result = resolve_placeholders(text, contexts={"known-id": ctx}, language="en")
    assert "{{cite:fabricated-id}}" not in result
    assert "Section 1 of Act, 2020" in result


def test_resolve_placeholders_handles_no_placeholders() -> None:
    from app.rag.citation import resolve_placeholders

    text = "No citations in this text."
    result = resolve_placeholders(text, contexts={}, language="en")
    assert result == text
