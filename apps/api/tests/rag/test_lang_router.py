"""Tests for Bengali Unicode-block language router (FR-QR-2)."""

from __future__ import annotations


def test_pure_bengali_returns_bn() -> None:
    from app.rag.lang_router import detect_language

    text = "শ্রমিকের সাপ্তাহিক ছুটি কত দিন?"
    lang, conf = detect_language(text)
    assert lang == "bn"
    assert conf >= 0.70


def test_pure_english_returns_en() -> None:
    from app.rag.lang_router import detect_language

    text = "What is the weekly holiday for workers?"
    lang, conf = detect_language(text)
    assert lang == "en"
    assert conf >= 0.85


def test_mixed_script_returns_mixed() -> None:
    from app.rag.lang_router import detect_language

    text = "section 103 ধারা একশত তিন"
    lang, conf = detect_language(text)
    assert lang == "mixed"
    assert 0.0 < conf <= 1.0


def test_empty_string_returns_en() -> None:
    from app.rag.lang_router import detect_language

    lang, conf = detect_language("")
    assert lang == "en"
    assert conf == 1.0


def test_whitespace_only_returns_en() -> None:
    from app.rag.lang_router import detect_language

    lang, conf = detect_language("   \t\n  ")
    assert lang == "en"
    assert conf == 1.0


def test_confidence_in_unit_interval() -> None:
    from app.rag.lang_router import detect_language

    for text in ["hello", "আমি", "hello আমি", ""]:
        _, conf = detect_language(text)
        assert 0.0 <= conf <= 1.0, f"confidence out of range for {text!r}: {conf}"


def test_high_bengali_coverage_threshold() -> None:
    from app.rag.lang_router import detect_language

    # 70 Bengali chars, 30 ASCII → ratio=0.70 → should be "bn"
    text = "আ" * 70 + "a" * 30
    lang, _ = detect_language(text)
    assert lang == "bn"


def test_low_bengali_coverage_threshold() -> None:
    from app.rag.lang_router import detect_language

    # 10 Bengali chars, 90 ASCII → ratio=0.10 → should be "en"
    text = "আ" * 10 + "a" * 90
    lang, _ = detect_language(text)
    assert lang == "en"


def test_detected_language_type() -> None:
    from app.rag.lang_router import detect_language

    lang, conf = detect_language("test")
    assert isinstance(lang, str)
    assert lang in ("bn", "en", "mixed")
    assert isinstance(conf, float)
