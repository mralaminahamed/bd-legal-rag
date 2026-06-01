"""Tests for eval/metrics.py — five legal-domain evaluation metrics (FR-EV-2).

Covers section_citation_accuracy, context_recall_at_k, language_routing_accuracy,
decline_accuracy, and answer_edit_distance across hit, miss, edge-case, and
empty-list scenarios.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from datetime import date

import pytest

from eval.metrics import (
    EvalRecord,
    EvalResult,
    Pair,
    answer_edit_distance,
    context_recall_at_k,
    decline_accuracy,
    language_routing_accuracy,
    section_citation_accuracy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(
    *,
    id: str = "test-001",
    language: str = "en",
    act_slug: str | None = "labour-act-2006",
    question: str = "What is the weekly holiday?",
    expected_act: str | None = "The Bangladesh Labour Act, 2006",
    expected_section: str | None = "103",
    expected_subsection: str | None = None,
    reference_summary: str | None = "Workers get one weekly holiday.",
    must_cite: bool = True,
    category: str = "factual",
    should_decline: bool = False,
    as_of_date: date | None = None,
) -> EvalRecord:
    """Build an EvalRecord with sensible defaults for testing."""
    return EvalRecord(
        id=id,
        language=language,
        act_slug=act_slug,
        question=question,
        expected_act=expected_act,
        expected_section=expected_section,
        expected_subsection=expected_subsection,
        reference_summary=reference_summary,
        must_cite=must_cite,
        category=category,
        should_decline=should_decline,
        as_of_date=as_of_date,
    )


def _result(
    *,
    detected_language: str = "en",
    declined: bool = False,
    retrieved_sections: list[str] | None = None,
    answer: str = "Workers get one weekly holiday.",
) -> EvalResult:
    """Build an EvalResult with sensible defaults for testing."""
    return EvalResult(
        detected_language=detected_language,
        declined=declined,
        retrieved_sections=retrieved_sections if retrieved_sections is not None else ["103"],
        answer=answer,
    )


def _pair(rec: EvalRecord, res: EvalResult) -> Pair:
    return (rec, res)


# ---------------------------------------------------------------------------
# section_citation_accuracy
# ---------------------------------------------------------------------------


class TestSectionCitationAccuracy:
    """Tests for section_citation_accuracy."""

    def test_hit_returns_one(self) -> None:
        """Top-1 section matches expected_section → accuracy = 1.0."""
        rec = _record(expected_section="103")
        res = _result(retrieved_sections=["103", "104", "105"])
        assert section_citation_accuracy([_pair(rec, res)]) == 1.0

    def test_miss_returns_zero(self) -> None:
        """Top-1 section does not match expected_section → accuracy = 0.0."""
        rec = _record(expected_section="103")
        res = _result(retrieved_sections=["104", "105"])
        assert section_citation_accuracy([_pair(rec, res)]) == 0.0

    def test_skip_declined_record(self) -> None:
        """should_decline=True records are excluded; eligible hit gives 1.0."""
        declined_rec = _record(id="d1", should_decline=True, expected_section="103")
        declined_res = _result(retrieved_sections=["103"])
        hit_rec = _record(id="h1", expected_section="50")
        hit_res = _result(retrieved_sections=["50"])
        pairs = [_pair(declined_rec, declined_res), _pair(hit_rec, hit_res)]
        assert section_citation_accuracy(pairs) == 1.0

    def test_skip_no_expected_section(self) -> None:
        """Records with no expected_section are excluded."""
        no_sec_rec = _record(id="n1", expected_section=None)
        no_sec_res = _result(retrieved_sections=["103"])
        miss_rec = _record(id="m1", expected_section="99")
        miss_res = _result(retrieved_sections=["1"])
        pairs = [_pair(no_sec_rec, no_sec_res), _pair(miss_rec, miss_res)]
        assert section_citation_accuracy(pairs) == 0.0

    def test_empty_pairs_returns_one(self) -> None:
        """Empty pair list returns 1.0 (no eligible records)."""
        assert section_citation_accuracy([]) == 1.0

    def test_all_declined_returns_one(self) -> None:
        """All records declined → no eligible records → 1.0."""
        rec = _record(should_decline=True, expected_section="103")
        res = _result(retrieved_sections=["103"])
        assert section_citation_accuracy([_pair(rec, res)]) == 1.0

    def test_empty_retrieved_sections_is_miss(self) -> None:
        """No retrieved sections → miss (no top-1 to match)."""
        rec = _record(expected_section="103")
        res = _result(retrieved_sections=[])
        assert section_citation_accuracy([_pair(rec, res)]) == 0.0

    def test_partial_hit_counts_correctly(self) -> None:
        """One hit and one miss in a batch → 0.5."""
        hit_rec = _record(id="h1", expected_section="103")
        hit_res = _result(retrieved_sections=["103"])
        miss_rec = _record(id="m1", expected_section="200")
        miss_res = _result(retrieved_sections=["1"])
        pairs = [_pair(hit_rec, hit_res), _pair(miss_rec, miss_res)]
        assert section_citation_accuracy(pairs) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# context_recall_at_k
# ---------------------------------------------------------------------------


class TestContextRecallAtK:
    """Tests for context_recall_at_k."""

    def test_hit_within_k(self) -> None:
        """Expected section appears within top-k → 1.0."""
        rec = _record(expected_section="103")
        res = _result(retrieved_sections=["1", "2", "103", "104", "105"])
        assert context_recall_at_k([_pair(rec, res)], k=5) == 1.0

    def test_miss_outside_k(self) -> None:
        """Expected section beyond top-k → 0.0."""
        rec = _record(expected_section="103")
        res = _result(retrieved_sections=["1", "2", "3", "4", "5", "103"])
        assert context_recall_at_k([_pair(rec, res)], k=5) == 0.0

    def test_boundary_exactly_at_k(self) -> None:
        """Expected section is exactly at position k (0-indexed k-1) → 1.0."""
        rec = _record(expected_section="103")
        # k=3, so indices 0,1,2 — section at index 2 should be included
        res = _result(retrieved_sections=["1", "2", "103", "4"])
        assert context_recall_at_k([_pair(rec, res)], k=3) == 1.0

    def test_miss_just_outside_boundary(self) -> None:
        """Expected section at position k+1 → excluded → 0.0."""
        rec = _record(expected_section="103")
        # k=2, indices 0,1 — section at index 2 is outside
        res = _result(retrieved_sections=["1", "2", "103"])
        assert context_recall_at_k([_pair(rec, res)], k=2) == 0.0

    def test_skip_declined(self) -> None:
        """Declined records excluded; only eligible hit counted."""
        declined_rec = _record(id="d1", should_decline=True, expected_section="103")
        declined_res = _result(retrieved_sections=["103"])
        hit_rec = _record(id="h1", expected_section="50")
        hit_res = _result(retrieved_sections=["50", "51"])
        pairs = [_pair(declined_rec, declined_res), _pair(hit_rec, hit_res)]
        assert context_recall_at_k(pairs, k=5) == 1.0

    def test_empty_pairs_returns_one(self) -> None:
        """Empty pair list → 1.0."""
        assert context_recall_at_k([], k=5) == 1.0

    def test_default_k_is_five(self) -> None:
        """Default k=5; section at index 4 is included."""
        rec = _record(expected_section="103")
        res = _result(retrieved_sections=["1", "2", "3", "4", "103"])
        assert context_recall_at_k([_pair(rec, res)]) == 1.0


# ---------------------------------------------------------------------------
# language_routing_accuracy
# ---------------------------------------------------------------------------


class TestLanguageRoutingAccuracy:
    """Tests for language_routing_accuracy."""

    def test_correct_routing_en(self) -> None:
        """detected_language matches record.language for English."""
        rec = _record(language="en")
        res = _result(detected_language="en")
        assert language_routing_accuracy([_pair(rec, res)]) == 1.0

    def test_correct_routing_bn(self) -> None:
        """detected_language matches record.language for Bengali."""
        rec = _record(language="bn")
        res = _result(detected_language="bn")
        assert language_routing_accuracy([_pair(rec, res)]) == 1.0

    def test_mismatch_routing(self) -> None:
        """detected_language does not match → 0.0."""
        rec = _record(language="bn")
        res = _result(detected_language="en")
        assert language_routing_accuracy([_pair(rec, res)]) == 0.0

    def test_mixed_routing_partial(self) -> None:
        """One correct, one wrong → 0.5."""
        rec1 = _record(id="r1", language="en")
        res1 = _result(detected_language="en")
        rec2 = _record(id="r2", language="bn")
        res2 = _result(detected_language="en")
        pairs = [_pair(rec1, res1), _pair(rec2, res2)]
        assert language_routing_accuracy(pairs) == pytest.approx(0.5)

    def test_empty_pairs_returns_one(self) -> None:
        """Empty pair list → 1.0."""
        assert language_routing_accuracy([]) == 1.0


# ---------------------------------------------------------------------------
# decline_accuracy
# ---------------------------------------------------------------------------


class TestDeclineAccuracy:
    """Tests for decline_accuracy."""

    def test_correct_decline(self) -> None:
        """should_decline=True and declined=True → 1.0."""
        rec = _record(should_decline=True)
        res = _result(declined=True)
        assert decline_accuracy([_pair(rec, res)]) == 1.0

    def test_missed_decline(self) -> None:
        """should_decline=True but declined=False → 0.0."""
        rec = _record(should_decline=True)
        res = _result(declined=False)
        assert decline_accuracy([_pair(rec, res)]) == 0.0

    def test_false_positive_decline(self) -> None:
        """should_decline=False but declined=True → 0.0."""
        rec = _record(should_decline=False)
        res = _result(declined=True)
        assert decline_accuracy([_pair(rec, res)]) == 0.0

    def test_correct_non_decline(self) -> None:
        """should_decline=False and declined=False → 1.0."""
        rec = _record(should_decline=False)
        res = _result(declined=False)
        assert decline_accuracy([_pair(rec, res)]) == 1.0

    def test_mixed_decline_accuracy(self) -> None:
        """Two correct, two incorrect → 0.5."""
        pairs: list[Pair] = [
            _pair(_record(id="a", should_decline=True), _result(declined=True)),
            _pair(_record(id="b", should_decline=False), _result(declined=False)),
            _pair(_record(id="c", should_decline=True), _result(declined=False)),
            _pair(_record(id="d", should_decline=False), _result(declined=True)),
        ]
        assert decline_accuracy(pairs) == pytest.approx(0.5)

    def test_empty_pairs_returns_one(self) -> None:
        """Empty pair list → 1.0."""
        assert decline_accuracy([]) == 1.0


# ---------------------------------------------------------------------------
# answer_edit_distance
# ---------------------------------------------------------------------------


class TestAnswerEditDistance:
    """Tests for answer_edit_distance."""

    def test_identical_answer_returns_zero(self) -> None:
        """Identical answer and reference_summary → distance = 0.0."""
        text = "Workers get one weekly holiday."
        rec = _record(reference_summary=text)
        res = _result(answer=text, declined=False)
        assert answer_edit_distance([_pair(rec, res)]) == pytest.approx(0.0)

    def test_completely_different_returns_nonzero(self) -> None:
        """Entirely different strings → distance > 0."""
        rec = _record(reference_summary="abc")
        res = _result(answer="xyz", declined=False)
        dist = answer_edit_distance([_pair(rec, res)])
        assert dist > 0.0
        assert dist <= 1.0

    def test_skip_declined_records(self) -> None:
        """Declined records are excluded; eligible identical pair → 0.0."""
        declined_rec = _record(id="d1", should_decline=True, reference_summary="abc")
        declined_res = _result(declined=True, answer="xyz")
        eligible_rec = _record(id="e1", reference_summary="same text")
        eligible_res = _result(declined=False, answer="same text")
        pairs = [_pair(declined_rec, declined_res), _pair(eligible_rec, eligible_res)]
        assert answer_edit_distance(pairs) == pytest.approx(0.0)

    def test_skip_no_reference_summary(self) -> None:
        """Records without reference_summary are excluded."""
        no_ref_rec = _record(id="n1", reference_summary=None)
        no_ref_res = _result(declined=False, answer="something")
        eligible_rec = _record(id="e1", reference_summary="hello")
        eligible_res = _result(declined=False, answer="hello")
        pairs = [_pair(no_ref_rec, no_ref_res), _pair(eligible_rec, eligible_res)]
        assert answer_edit_distance(pairs) == pytest.approx(0.0)

    def test_empty_pairs_returns_zero(self) -> None:
        """Empty pair list → 0.0 (no eligible records)."""
        assert answer_edit_distance([]) == pytest.approx(0.0)

    def test_all_declined_returns_zero(self) -> None:
        """All declined → no eligible records → 0.0."""
        rec = _record(should_decline=True, reference_summary="Some text.")
        res = _result(declined=True, answer="Different answer.")
        assert answer_edit_distance([_pair(rec, res)]) == pytest.approx(0.0)

    def test_distance_between_zero_and_one(self) -> None:
        """Partially similar strings produce distance in [0, 1]."""
        rec = _record(reference_summary="The quick brown fox jumps over the lazy dog.")
        res = _result(answer="The quick brown cat jumps over the lazy dog.", declined=False)
        dist = answer_edit_distance([_pair(rec, res)])
        assert 0.0 < dist < 1.0

    def test_average_over_multiple_eligible(self) -> None:
        """Average distance is computed over all eligible pairs."""
        # pair 1: identical → distance 0.0
        text = "Same sentence here."
        rec1 = _record(id="r1", reference_summary=text)
        res1 = _result(answer=text, declined=False)
        # pair 2: completely different — force distance ~1.0 via non-overlapping strings
        rec2 = _record(id="r2", reference_summary="aaa")
        res2 = _result(answer="zzz", declined=False)
        pairs = [_pair(rec1, res1), _pair(rec2, res2)]
        dist = answer_edit_distance(pairs)
        # distance must be strictly between 0 and 1 (average of 0.0 and something > 0)
        assert 0.0 < dist <= 1.0
