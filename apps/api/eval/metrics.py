"""Legal-domain evaluation metrics (FR-EV-2).

Five metrics over (EvalRecord, EvalResult) pairs:
  - section_citation_accuracy: top-1 retrieved section == expected_section
  - context_recall_at_k: expected_section in top-k retrieved sections
  - language_routing_accuracy: detected_language == record.language
  - decline_accuracy: should_decline == result.declined for all records
  - answer_edit_distance: normalised SequenceMatcher ratio vs reference_summary

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EvalRecord:
    """A single entry from the golden evaluation dataset.

    Attributes:
        id: Unique identifier for the record (e.g. ``"labour-2006-bn-001"``).
        language: Expected query language — ``"bn"`` or ``"en"``.
        act_slug: URL slug of the Act this question targets, or ``None`` for
            cross-Act queries.
        question: The user-facing question string (may be Bengali or English).
        expected_act: Human-readable Act title, or ``None`` when not applicable.
        expected_section: Section number the correct answer must cite, or
            ``None`` when the question is not section-specific.
        expected_subsection: Subsection identifier, or ``None``.
        reference_summary: Short authoritative summary used for edit-distance
            scoring, or ``None`` when no reference exists.
        must_cite: Whether the response must include a citation.
        category: Question category (e.g. ``"factual"``, ``"procedural"``).
        should_decline: ``True`` when the system must decline the query (advice-
            seeking) rather than answer it.
        as_of_date: Effective date for the query, or ``None`` for today.
    """

    id: str
    language: str
    act_slug: str | None
    question: str
    expected_act: str | None
    expected_section: str | None
    expected_subsection: str | None
    reference_summary: str | None
    must_cite: bool
    category: str
    should_decline: bool
    as_of_date: date | None


@dataclass
class EvalResult:
    """System output produced for a single EvalRecord.

    Attributes:
        detected_language: Language the system routed the query to —
            ``"bn"``, ``"en"``, or ``"mixed"``.
        declined: ``True`` when the system declined to answer.
        retrieved_sections: Section numbers returned by retrieval, in rank
            order (highest-scoring first).
        answer: The generated answer text (empty string when declined).
    """

    detected_language: str
    declined: bool
    retrieved_sections: list[str]
    answer: str


Pair = tuple[EvalRecord, EvalResult]


def section_citation_accuracy(pairs: list[Pair]) -> float:
    """Compute the fraction of eligible records where top-1 section is correct.

    An eligible record must have ``should_decline=False`` and a non-``None``
    ``expected_section``. Records failing either condition are skipped.

    Args:
        pairs: Sequence of ``(EvalRecord, EvalResult)`` pairs to evaluate.

    Returns:
        Fraction in ``[0.0, 1.0]`` of eligible records whose top-1 retrieved
        section exactly matches ``expected_section``.  Returns ``1.0`` when
        there are no eligible records.
    """
    hits = 0
    total = 0
    for record, result in pairs:
        if record.should_decline or record.expected_section is None:
            continue
        total += 1
        top1 = result.retrieved_sections[0] if result.retrieved_sections else None
        if top1 == record.expected_section:
            hits += 1
    return 1.0 if total == 0 else hits / total


def context_recall_at_k(pairs: list[Pair], k: int = 5) -> float:
    """Compute the fraction of eligible records where expected_section is in top-k.

    An eligible record must have ``should_decline=False`` and a non-``None``
    ``expected_section``.

    Args:
        pairs: Sequence of ``(EvalRecord, EvalResult)`` pairs to evaluate.
        k: Number of top retrieved sections to inspect.

    Returns:
        Fraction in ``[0.0, 1.0]`` of eligible records whose ``expected_section``
        appears anywhere in the first ``k`` retrieved sections.  Returns ``1.0``
        when there are no eligible records.
    """
    hits = 0
    total = 0
    for record, result in pairs:
        if record.should_decline or record.expected_section is None:
            continue
        total += 1
        top_k = result.retrieved_sections[:k]
        if record.expected_section in top_k:
            hits += 1
    return 1.0 if total == 0 else hits / total


def language_routing_accuracy(pairs: list[Pair]) -> float:
    """Compute the fraction of records where language routing is correct.

    Every record in ``pairs`` is evaluated regardless of ``should_decline`` or
    ``expected_section``, because routing happens before decline detection.

    Args:
        pairs: Sequence of ``(EvalRecord, EvalResult)`` pairs to evaluate.

    Returns:
        Fraction in ``[0.0, 1.0]`` of records where ``result.detected_language``
        matches ``record.language``.  Returns ``1.0`` when ``pairs`` is empty.
    """
    if not pairs:
        return 1.0
    correct = sum(
        1 for record, result in pairs if result.detected_language == record.language
    )
    return correct / len(pairs)


def decline_accuracy(pairs: list[Pair]) -> float:
    """Compute the fraction of records where the decline decision is correct.

    A correct decision means ``result.declined == record.should_decline`` —
    covering both true declines and correct non-declines.

    Args:
        pairs: Sequence of ``(EvalRecord, EvalResult)`` pairs to evaluate.

    Returns:
        Fraction in ``[0.0, 1.0]`` of records with a correct decline decision.
        Returns ``1.0`` when ``pairs`` is empty.
    """
    if not pairs:
        return 1.0
    correct = sum(
        1 for record, result in pairs if result.declined == record.should_decline
    )
    return correct / len(pairs)


def answer_edit_distance(pairs: list[Pair]) -> float:
    """Compute the mean normalised edit distance between answers and references.

    Only non-declined records that have a ``reference_summary`` are evaluated.
    The distance is derived from ``difflib.SequenceMatcher.ratio()``:

        distance = 1.0 - ratio

    so ``0.0`` means identical and ``1.0`` means completely different.

    Args:
        pairs: Sequence of ``(EvalRecord, EvalResult)`` pairs to evaluate.

    Returns:
        Mean normalised distance in ``[0.0, 1.0]`` over all eligible records.
        Returns ``0.0`` when there are no eligible records.
    """
    distances: list[float] = []
    for record, result in pairs:
        if result.declined or record.reference_summary is None:
            continue
        ratio = difflib.SequenceMatcher(
            None, record.reference_summary, result.answer
        ).ratio()
        distances.append(1.0 - ratio)
    return 0.0 if not distances else sum(distances) / len(distances)
