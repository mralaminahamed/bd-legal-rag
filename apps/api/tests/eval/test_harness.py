"""Unit tests for eval/harness.py — offline eval harness (FR-EV-1/3/5).

Tests cover load_golden_dataset, extract_section_from_hierarchy_path,
compute_metrics, persist_run / load_previous_run, and check_thresholds.
Full async end-to-end execution is NOT tested here (requires a live DB);
only pure logic and file I/O are exercised so the suite stays offline.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from eval.harness import (
    check_thresholds,
    compute_metrics,
    extract_section_from_hierarchy_path,
    load_golden_dataset,
    load_previous_run,
    persist_run,
)
from eval.metrics import EvalRecord, EvalResult, Pair


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


# ---------------------------------------------------------------------------
# load_golden_dataset
# ---------------------------------------------------------------------------


class TestLoadGoldenDataset:
    """Tests for load_golden_dataset()."""

    def test_loads_file(self) -> None:
        """load_golden_dataset() must return a non-empty list."""
        records = load_golden_dataset()
        assert len(records) > 0

    def test_at_least_sixty_records(self) -> None:
        """Golden dataset must have ≥ 60 records (per spec)."""
        records = load_golden_dataset()
        assert len(records) >= 60

    def test_at_least_ten_advice_seeking(self) -> None:
        """At least 10 records must be advice-seeking (should_decline=True, category advice_seeking)."""
        records = load_golden_dataset()
        advice = [r for r in records if r.category == "advice_seeking"]
        assert len(advice) >= 10

    def test_at_least_ten_out_of_scope(self) -> None:
        """At least 10 records must be out-of-scope (category out_of_scope)."""
        records = load_golden_dataset()
        oos = [r for r in records if r.category == "out_of_scope"]
        assert len(oos) >= 10

    def test_records_are_eval_record_instances(self) -> None:
        """All items must be EvalRecord instances."""
        records = load_golden_dataset()
        assert all(isinstance(r, EvalRecord) for r in records)

    def test_as_of_date_parsed_or_none(self) -> None:
        """Records with a non-null as_of_date must have a date instance; null → None."""
        records = load_golden_dataset()
        for r in records:
            if r.as_of_date is not None:
                assert isinstance(r.as_of_date, date)

    def test_should_decline_fields_consistent(self) -> None:
        """Advice-seeking and out-of-scope records must have should_decline=True."""
        records = load_golden_dataset()
        for r in records:
            if r.category in ("advice_seeking", "out_of_scope"):
                assert r.should_decline is True, (
                    f"record {r.id!r} category={r.category!r} should have should_decline=True"
                )


# ---------------------------------------------------------------------------
# extract_section_from_hierarchy_path
# ---------------------------------------------------------------------------


class TestExtractSectionFromHierarchyPath:
    """Tests for extract_section_from_hierarchy_path()."""

    def test_standard_section_number(self) -> None:
        """'Section 103: Weekly holiday' → '103'."""
        path = "The Bangladesh Labour Act, 2006 > Part IX: Leave > Section 103: Weekly holiday"
        assert extract_section_from_hierarchy_path(path) == "103"

    def test_section_without_title(self) -> None:
        """'Section 2' (no colon/title) → '2'."""
        path = "Some Act > Section 2"
        assert extract_section_from_hierarchy_path(path) == "2"

    def test_section_with_colon_title(self) -> None:
        """'Section 116: Annual leave' → '116'."""
        path = "Labour Act > Part IX > Section 116: Annual leave"
        assert extract_section_from_hierarchy_path(path) == "116"

    def test_no_section_returns_none(self) -> None:
        """Path with no 'Section' token returns None."""
        path = "The Bangladesh Labour Act, 2006 > Part IX: Leave"
        assert extract_section_from_hierarchy_path(path) is None

    def test_empty_path_returns_none(self) -> None:
        """Empty string returns None."""
        assert extract_section_from_hierarchy_path("") is None

    def test_section_at_root_level(self) -> None:
        """Top-level section in a path returns its number."""
        path = "Section 80: Share transfer"
        assert extract_section_from_hierarchy_path(path) == "80"

    def test_large_section_number(self) -> None:
        """Three-digit section numbers are extracted correctly."""
        path = "Companies Act > Part XII > Section 391: Mergers"
        assert extract_section_from_hierarchy_path(path) == "391"


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    """Tests for compute_metrics()."""

    def _make_pairs(self) -> list[Pair]:
        """Return a small, mixed set of pairs for metric sanity checks."""
        pairs: list[Pair] = [
            (_record(id="a", expected_section="103"), _result(retrieved_sections=["103"])),
            (_record(id="b", language="bn"), _result(detected_language="bn")),
            (
                _record(id="c", should_decline=True, expected_section=None),
                _result(declined=True),
            ),
        ]
        return pairs

    def test_returns_all_five_keys(self) -> None:
        """compute_metrics() must return exactly the five documented keys."""
        pairs = self._make_pairs()
        metrics = compute_metrics(pairs)
        expected_keys = {
            "section_citation_accuracy",
            "context_recall_at_5",
            "language_routing_accuracy",
            "decline_accuracy",
            "answer_edit_distance",
        }
        assert set(metrics.keys()) == expected_keys

    def test_all_values_in_range(self) -> None:
        """All metric values must be in [0.0, 1.0]."""
        pairs = self._make_pairs()
        metrics = compute_metrics(pairs)
        for key, value in metrics.items():
            assert 0.0 <= value <= 1.0, f"{key}={value} out of range"

    def test_empty_pairs_all_ones_or_zeros(self) -> None:
        """Empty pair list: accuracy metrics → 1.0, edit distance → 0.0."""
        metrics = compute_metrics([])
        assert metrics["section_citation_accuracy"] == 1.0
        assert metrics["context_recall_at_5"] == 1.0
        assert metrics["language_routing_accuracy"] == 1.0
        assert metrics["decline_accuracy"] == 1.0
        assert metrics["answer_edit_distance"] == 0.0

    def test_perfect_pairs(self) -> None:
        """All-correct pairs yield 1.0 on accuracy metrics."""
        pairs: list[Pair] = [
            (
                _record(id="p1", language="en", expected_section="103"),
                _result(detected_language="en", retrieved_sections=["103"]),
            ),
            (
                _record(id="p2", language="bn", expected_section="2"),
                _result(detected_language="bn", retrieved_sections=["2"]),
            ),
        ]
        metrics = compute_metrics(pairs)
        assert metrics["section_citation_accuracy"] == 1.0
        assert metrics["language_routing_accuracy"] == 1.0
        assert metrics["decline_accuracy"] == 1.0


# ---------------------------------------------------------------------------
# persist_run / load_previous_run
# ---------------------------------------------------------------------------


class TestPersistRun:
    """Tests for persist_run() and load_previous_run()."""

    def test_write_and_read_back(self, tmp_path: Path) -> None:
        """persist_run writes a JSON file; load_previous_run reads it back."""
        metrics = {
            "section_citation_accuracy": 0.90,
            "context_recall_at_5": 0.95,
            "language_routing_accuracy": 0.98,
            "decline_accuracy": 0.97,
            "answer_edit_distance": 0.12,
        }
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        path = persist_run(
            metrics=metrics,
            record_count=84,
            prompt_version="v1",
            retrieval_config={"top_k": 8, "top_n": 40},
            reranker_version="rerank-multilingual-v3.0",
            runs_dir=runs_dir,
        )

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["metrics"]["section_citation_accuracy"] == pytest.approx(0.90)
        assert data["record_count"] == 84
        assert data["prompt_version"] == "v1"
        assert data["reranker_version"] == "rerank-multilingual-v3.0"

    def test_json_file_has_iso_timestamp_in_name(self, tmp_path: Path) -> None:
        """File name must start with an ISO timestamp component (YYYY-MM-DDT...)."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        path = persist_run(
            metrics={"section_citation_accuracy": 1.0},
            record_count=1,
            prompt_version="v1",
            retrieval_config={},
            reranker_version="rr-v3",
            runs_dir=runs_dir,
        )
        # Pattern: YYYY-MM-DDT…
        assert path.name[4] == "-", f"Expected ISO timestamp in name, got {path.name!r}"
        assert path.name[7] == "-", f"Expected ISO timestamp in name, got {path.name!r}"
        assert "T" in path.name, f"Expected 'T' separator in name, got {path.name!r}"

    def test_load_previous_run_returns_none_for_empty_dir(self, tmp_path: Path) -> None:
        """load_previous_run returns None when runs_dir has no JSON files."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        assert load_previous_run("v1", runs_dir) is None

    def test_load_previous_run_returns_latest(self, tmp_path: Path) -> None:
        """load_previous_run returns the data dict from the most recent file."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Write two files with distinct metrics; microsecond precision in filename
        # ensures the second file always sorts after the first.
        metrics_old = {"section_citation_accuracy": 0.80}
        metrics_new = {"section_citation_accuracy": 0.91}

        persist_run(
            metrics=metrics_old,
            record_count=5,
            prompt_version="v1",
            retrieval_config={},
            reranker_version="rr-v3",
            runs_dir=runs_dir,
        )
        persist_run(
            metrics=metrics_new,
            record_count=5,
            prompt_version="v1",
            retrieval_config={},
            reranker_version="rr-v3",
            runs_dir=runs_dir,
        )

        # The file with the lexicographically latest name must contain metrics_new.
        all_files = sorted((runs_dir).glob("*.json"))
        assert len(all_files) == 2
        latest_data = json.loads(all_files[-1].read_text())
        assert latest_data["metrics"]["section_citation_accuracy"] == pytest.approx(0.91)

        result = load_previous_run("v1", runs_dir)
        assert result is not None
        assert result.metrics["section_citation_accuracy"] == pytest.approx(0.91)

    def test_persist_run_returns_path_object(self, tmp_path: Path) -> None:
        """persist_run returns a Path pointing to the written file."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        path = persist_run(
            metrics={},
            record_count=0,
            prompt_version="v1",
            retrieval_config={},
            reranker_version="rr-v3",
            runs_dir=runs_dir,
        )
        assert isinstance(path, Path)
        assert path.suffix == ".json"


# ---------------------------------------------------------------------------
# check_thresholds
# ---------------------------------------------------------------------------


class TestCheckThresholds:
    """Tests for check_thresholds()."""

    def test_all_pass_returns_true(self) -> None:
        """All metrics above threshold → True."""
        metrics = {
            "section_citation_accuracy": 0.90,
            "language_routing_accuracy": 0.97,
            "decline_accuracy": 0.96,
        }
        assert check_thresholds(metrics) is True

    def test_section_citation_fails_returns_false(self) -> None:
        """section_citation_accuracy below 0.85 → False."""
        metrics = {
            "section_citation_accuracy": 0.80,
            "language_routing_accuracy": 0.97,
            "decline_accuracy": 0.96,
        }
        assert check_thresholds(metrics) is False

    def test_language_routing_fails_returns_false(self) -> None:
        """language_routing_accuracy below 0.95 → False."""
        metrics = {
            "section_citation_accuracy": 0.90,
            "language_routing_accuracy": 0.93,
            "decline_accuracy": 0.96,
        }
        assert check_thresholds(metrics) is False

    def test_decline_accuracy_fails_returns_false(self) -> None:
        """decline_accuracy below 0.95 → False."""
        metrics = {
            "section_citation_accuracy": 0.90,
            "language_routing_accuracy": 0.97,
            "decline_accuracy": 0.94,
        }
        assert check_thresholds(metrics) is False

    def test_exactly_at_threshold_passes(self) -> None:
        """Metrics exactly at threshold boundaries → True."""
        metrics = {
            "section_citation_accuracy": 0.85,
            "language_routing_accuracy": 0.95,
            "decline_accuracy": 0.95,
        }
        assert check_thresholds(metrics) is True

    def test_all_fail_returns_false(self) -> None:
        """All metrics below threshold → False."""
        metrics = {
            "section_citation_accuracy": 0.50,
            "language_routing_accuracy": 0.50,
            "decline_accuracy": 0.50,
        }
        assert check_thresholds(metrics) is False
