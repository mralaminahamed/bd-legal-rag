"""Offline evaluation harness — full pipeline eval (FR-EV-1/3/5).

Runs the complete retrieve → generate → safety pipeline against the golden
dataset with external calls patched:

- Embedders (CohereEmbedder / OllamaEmbedder): patched to return a zero vector.
- Cohere reranker: patched to sort by whether ``hierarchy_path`` contains the
  expected section, simulating a perfect-precision reranker.
- LLM factory: patched to return a mock provider that returns
  ``reference_summary + " {{cite:00000000-…-0001}}"`` (or empty string when
  no summary).

``detect_language`` and ``decline_gate.classify`` run UNPATCHED so the harness
measures real language-routing accuracy and real decline accuracy.

Usage::

    cd apps/api
    uv run python -m eval.harness            # exits 0 on pass, 1 on threshold fail

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import Settings, get_settings
from app.db.engine import get_sessionmaker
from app.llm.base import CompletionResult, TokenUsage
from app.rag.retriever import RetrievedChunk

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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATASET_PATH = Path(__file__).parent / "dataset" / "golden.jsonl"
_RUNS_DIR = Path(__file__).parent / "runs"

_THRESHOLDS: dict[str, float] = {
    "section_citation_accuracy": 0.85,
    "language_routing_accuracy": 0.95,
    "decline_accuracy": 0.95,
}

# Dummy UUIDs used in the mock LLM citation placeholder
_MOCK_CHUNK_ID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_golden_dataset(path: Path | None = None) -> list[EvalRecord]:
    """Load the bilingual golden evaluation dataset from JSONL.

    Args:
        path: Path to the ``.jsonl`` file; defaults to the canonical dataset
            at ``eval/dataset/golden.jsonl``.

    Returns:
        list[EvalRecord]: All records in the file, in order.
    """
    fpath = path or _DATASET_PATH
    records: list[EvalRecord] = []
    with fpath.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            aod: date | None = None
            if obj.get("as_of_date"):
                aod = date.fromisoformat(obj["as_of_date"])
            records.append(
                EvalRecord(
                    id=obj["id"],
                    language=obj["language"],
                    act_slug=obj.get("act_slug"),
                    question=obj["question"],
                    expected_act=obj.get("expected_act"),
                    expected_section=obj.get("expected_section"),
                    expected_subsection=obj.get("expected_subsection"),
                    reference_summary=obj.get("reference_summary"),
                    must_cite=bool(obj.get("must_cite", False)),
                    category=obj["category"],
                    should_decline=bool(obj.get("should_decline", False)),
                    as_of_date=aod,
                )
            )
    return records


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"\bSection\s+(\d+)", re.IGNORECASE)


def extract_section_from_hierarchy_path(hierarchy_path: str) -> str | None:
    """Extract the numeric section identifier from a hierarchy path string.

    Parses paths of the form::

        "... > Section 103: Weekly holiday"
        "... > Section 2"

    Args:
        hierarchy_path: Statutory breadcrumb string from a
            :class:`~app.rag.retriever.RetrievedChunk`.

    Returns:
        str | None: The section number string (e.g. ``"103"``), or ``None``
        when no ``Section <n>`` token is found.
    """
    # Scan from the right so the deepest (most specific) section wins.
    parts = hierarchy_path.split(" > ")
    for part in reversed(parts):
        m = _SECTION_RE.search(part)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Metrics aggregation
# ---------------------------------------------------------------------------


def compute_metrics(pairs: list[Pair]) -> dict[str, float]:
    """Aggregate the five standard metrics over a list of (record, result) pairs.

    Args:
        pairs: Sequence of ``(EvalRecord, EvalResult)`` pairs.

    Returns:
        dict[str, float]: Keys are
        ``section_citation_accuracy``, ``context_recall_at_5``,
        ``language_routing_accuracy``, ``decline_accuracy``, and
        ``answer_edit_distance``.
    """
    return {
        "section_citation_accuracy": section_citation_accuracy(pairs),
        "context_recall_at_5": context_recall_at_k(pairs, k=5),
        "language_routing_accuracy": language_routing_accuracy(pairs),
        "decline_accuracy": decline_accuracy(pairs),
        "answer_edit_distance": answer_edit_distance(pairs),
    }


# ---------------------------------------------------------------------------
# Threshold check
# ---------------------------------------------------------------------------


def check_thresholds(metrics: dict[str, float]) -> bool:
    """Check whether all gated metrics meet their CI thresholds.

    Args:
        metrics: Metrics dict as returned by :func:`compute_metrics`.

    Returns:
        bool: ``True`` when every gated metric meets or exceeds its threshold;
        ``False`` when any metric falls below.
    """
    for metric, threshold in _THRESHOLDS.items():
        value = metrics.get(metric, 0.0)
        if value < threshold:
            logger.warning(
                "threshold_fail metric=%s value=%.4f threshold=%.4f",
                metric,
                value,
                threshold,
            )
            return False
    return True


# ---------------------------------------------------------------------------
# Run persistence
# ---------------------------------------------------------------------------


@dataclass
class EvalRun:
    """Persisted record of a single harness execution.

    Attributes:
        timestamp: ISO-8601 UTC timestamp when the run completed.
        prompt_version: Active prompt version used during generation.
        reranker_version: Active reranker model version.
        retrieval_config: Snapshot of key retrieval parameters.
        metrics: Computed metric values.
        record_count: Number of golden records evaluated.
        run_id: Random UUID identifying this execution.
    """

    timestamp: str
    prompt_version: str
    reranker_version: str
    retrieval_config: dict[str, Any]
    metrics: dict[str, float]
    record_count: int
    run_id: str


def persist_run(
    *,
    metrics: dict[str, float],
    record_count: int,
    prompt_version: str,
    retrieval_config: dict[str, Any],
    reranker_version: str,
    runs_dir: Path | None = None,
) -> Path:
    """Write an :class:`EvalRun` as JSON to the runs directory.

    The file name is ``<ISO-timestamp>_<prompt_version>_<run_id>.json`` so that
    ``sorted()`` on the directory gives chronological order.

    Args:
        metrics: Metric values from :func:`compute_metrics`.
        record_count: Number of golden records evaluated.
        prompt_version: Active prompt version (e.g. ``"v1"``).
        retrieval_config: Snapshot of retrieval parameters.
        reranker_version: Active reranker model identifier.
        runs_dir: Directory to write runs into; defaults to
            ``eval/runs/``.

    Returns:
        Path: Path to the written JSON file.
    """
    rdir = runs_dir or _RUNS_DIR
    rdir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=UTC)
    run_id = str(uuid.uuid4())
    ts = now.strftime("%Y-%m-%dT%H-%M-%S-%f")
    filename = f"{ts}_{prompt_version}_{run_id}.json"

    run = EvalRun(
        timestamp=now.isoformat(),
        prompt_version=prompt_version,
        reranker_version=reranker_version,
        retrieval_config=retrieval_config,
        metrics=metrics,
        record_count=record_count,
        run_id=run_id,
    )
    path = rdir / filename
    path.write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")
    logger.info("eval_run_persisted path=%s", path)
    return path


def load_previous_run(
    prompt_version: str,
    runs_dir: Path = _RUNS_DIR,
    *,
    exclude: Path | None = None,
) -> EvalRun | None:
    """Load the most recent harness run matching a prompt version.

    Args:
        prompt_version: The ``prompt_version`` field value to filter on.
        runs_dir: Directory to search; defaults to ``eval/runs/``.
        exclude: Path to skip (e.g. the file just written in the current run).

    Returns:
        EvalRun | None: The most recent matching run, or ``None`` when no
        matching run files exist.
    """
    files = sorted(runs_dir.glob("*.json"), reverse=True)
    for f in files:
        if exclude is not None and f == exclude:
            continue
        data: dict[str, Any] = json.loads(f.read_text(encoding="utf-8"))
        if data.get("prompt_version") != prompt_version:
            continue
        return EvalRun(
            timestamp=data["timestamp"],
            prompt_version=data["prompt_version"],
            reranker_version=data["reranker_version"],
            retrieval_config=data["retrieval_config"],
            metrics=data["metrics"],
            record_count=data["record_count"],
            run_id=data["run_id"],
        )
    return None


# ---------------------------------------------------------------------------
# Per-Act / per-language breakdown helpers
# ---------------------------------------------------------------------------


def _breakdown_by_act(pairs: list[Pair]) -> dict[str, dict[str, float]]:
    """Compute section_citation_accuracy per act_slug.

    Args:
        pairs: Full list of (record, result) pairs.

    Returns:
        dict[str, dict[str, float]]: Mapping from act_slug to a dict with
        ``section_citation_accuracy`` and ``count`` keys.
    """
    by_act: dict[str, list[Pair]] = {}
    for record, result in pairs:
        slug = record.act_slug or "__no_act__"
        by_act.setdefault(slug, []).append((record, result))
    return {
        slug: {
            "section_citation_accuracy": section_citation_accuracy(act_pairs),
            "decline_accuracy": decline_accuracy(act_pairs),
            "count": float(len(act_pairs)),
        }
        for slug, act_pairs in by_act.items()
    }


def _breakdown_by_language(pairs: list[Pair]) -> dict[str, dict[str, float]]:
    """Compute per-language accuracy metrics.

    Args:
        pairs: Full list of (record, result) pairs.

    Returns:
        dict[str, dict[str, float]]: Mapping from language code to metric dict.
    """
    by_lang: dict[str, list[Pair]] = {}
    for record, result in pairs:
        by_lang.setdefault(record.language, []).append((record, result))
    return {
        lang: {
            "section_citation_accuracy": section_citation_accuracy(lang_pairs),
            "language_routing_accuracy": language_routing_accuracy(lang_pairs),
            "decline_accuracy": decline_accuracy(lang_pairs),
            "count": float(len(lang_pairs)),
        }
        for lang, lang_pairs in by_lang.items()
    }


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _build_mock_embedder(dim: int) -> MagicMock:
    """Return a mock embedder whose embed_query returns a zero vector.

    Args:
        dim: Embedding dimension (2560 for OllamaEmbedder).

    Returns:
        MagicMock: Mock with ``embed_query`` as an AsyncMock.
    """
    mock = MagicMock()
    mock.embed_query = AsyncMock(return_value=[0.0] * dim)
    mock.embed_documents = AsyncMock(return_value=[[0.0] * dim])
    return mock


def _build_mock_reranker(
    expected_section: str | None,
) -> Any:
    """Return an async side-effect function for the reranker patch.

    Sorts retrieved chunks so that chunks whose ``hierarchy_path`` contains
    the expected section appear first, simulating a correct reranker.

    Args:
        expected_section: Section number string to privilege.

    Returns:
        Coroutine function compatible with ``AsyncMock(side_effect=...)``.
    """

    async def _mock_rerank(
        query: str,
        candidates: list[RetrievedChunk],
        settings: Settings,
    ) -> list[RetrievedChunk]:
        def _rank_key(chunk: RetrievedChunk) -> int:
            if expected_section and f"Section {expected_section}" in chunk.hierarchy_path:
                return 0
            return 1

        return sorted(candidates, key=_rank_key)

    return _mock_rerank


def _build_mock_provider(reference_summary: str | None) -> MagicMock:
    """Return a mock LLM provider that returns a deterministic completion.

    For non-decline records with a reference summary: returns
    ``reference_summary + " {{cite:00000000-…-0001}}"``.
    Otherwise: returns an empty string.

    Args:
        reference_summary: The golden reference text, or ``None``.

    Returns:
        MagicMock: Mock provider with ``complete`` as an AsyncMock.
    """
    if reference_summary:
        text = f"{reference_summary} {{{{cite:{_MOCK_CHUNK_ID}}}}}"
    else:
        text = ""
    mock_provider = MagicMock()
    mock_provider.model = "mock-eval"
    mock_provider.complete = AsyncMock(
        return_value=CompletionResult(
            text=text,
            usage=TokenUsage(input_tokens=10, output_tokens=20),
            model="mock-eval",
        )
    )
    return mock_provider


# ---------------------------------------------------------------------------
# Single-record evaluation
# ---------------------------------------------------------------------------


async def _evaluate_record(
    record: EvalRecord,
    settings: Settings,
) -> EvalResult:
    """Run the full pipeline for one golden record and return an EvalResult.

    Patches embedders, reranker, and LLM factory before calling
    :func:`~app.rag.service.retrieve` and :func:`~app.rag.generator.generate`.
    ``detect_language`` and ``decline_gate.classify`` run UNPATCHED.

    Args:
        record: A single EvalRecord from the golden dataset.
        settings: Application settings (used for retrieval config).

    Returns:
        EvalResult: The system output for the record.
    """
    from app.rag.generator import generate
    from app.rag.service import retrieve

    embed_dim = settings.embed_dimensions
    mock_embedder = _build_mock_embedder(embed_dim)
    mock_reranker_fn = _build_mock_reranker(record.expected_section)
    mock_provider = _build_mock_provider(record.reference_summary)

    as_of = record.as_of_date  # may be None → retrieve() defaults to today

    with (
        patch("app.rag.service.OllamaEmbedder", return_value=mock_embedder),
        patch("app.rag.service.CohereEmbedder", return_value=mock_embedder),
        patch("app.rag.reranker.rerank", side_effect=mock_reranker_fn),
        patch("app.llm.factory.create_provider", return_value=mock_provider),
    ):
        async with get_sessionmaker()() as session:
            retrieval_result = await retrieve(
                session,
                record.question,
                settings,
                as_of_date=as_of,
            )
            gen_result = await generate(
                retrieval_result=retrieval_result,
                session=session,
                settings=settings,
            )

    # Extract section numbers from retrieved chunk hierarchy paths.
    retrieved_sections: list[str] = []
    for chunk in retrieval_result.chunks:
        sec = extract_section_from_hierarchy_path(chunk.hierarchy_path)
        if sec is not None:
            retrieved_sections.append(sec)

    return EvalResult(
        detected_language=retrieval_result.detected_language,
        declined=gen_result.declined,
        retrieved_sections=retrieved_sections,
        answer=gen_result.answer,
    )


# ---------------------------------------------------------------------------
# Main harness
# ---------------------------------------------------------------------------


async def _run_harness(settings: Settings) -> tuple[list[Pair], dict[str, float]]:
    """Execute the harness over all golden records and return pairs + metrics.

    Args:
        settings: Application settings.

    Returns:
        tuple[list[Pair], dict[str, float]]: All (record, result) pairs and
        the computed metric dict.
    """
    records = load_golden_dataset()
    pairs: list[Pair] = []
    errors = 0

    for i, record in enumerate(records, start=1):
        try:
            result = await _evaluate_record(record, settings)
            pairs.append((record, result))
            logger.debug(
                "eval record=%s detected_lang=%s declined=%s retrieved=%s",
                record.id,
                result.detected_language,
                result.declined,
                result.retrieved_sections[:3],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("eval_error record=%s: %s", record.id, exc)
            errors += 1
            # Produce a neutral result so metrics stay computable.
            pairs.append(
                (
                    record,
                    EvalResult(
                        detected_language="en",
                        declined=False,
                        retrieved_sections=[],
                        answer="",
                    ),
                )
            )

        if i % 10 == 0 or i == len(records):
            logger.info("eval progress %d/%d errors=%d", i, len(records), errors)

    metrics = compute_metrics(pairs)
    return pairs, metrics


def _print_report(
    metrics: dict[str, float],
    pairs: list[Pair],
    settings: Settings,
    run_path: Path,
) -> None:
    """Print a human-readable harness report to stdout.

    Args:
        metrics: Aggregate metric values.
        pairs: All (record, result) pairs.
        settings: Application settings (for configuration snapshot).
        run_path: Path to the persisted JSON run file.
    """
    divider = "=" * 64

    print(f"\n{divider}")
    print("  BD Legal RAG — Evaluation Harness Report")
    print(divider)
    print(f"  Run file : {run_path.name}")
    print(f"  Records  : {len(pairs)}")
    print(f"  Dataset  : {_DATASET_PATH}")
    print(divider)
    print("  AGGREGATE METRICS")
    print(divider)

    for key, value in metrics.items():
        threshold = _THRESHOLDS.get(key)
        if threshold is not None:
            status = "PASS" if value >= threshold else "FAIL"
            print(f"  {key:<40} {value:.4f}  [{status} >= {threshold}]")
        else:
            print(f"  {key:<40} {value:.4f}")

    print(divider)
    print("  PER-ACT BREAKDOWN (section_citation_accuracy)")
    print(divider)
    act_breakdown = _breakdown_by_act(pairs)
    for slug, act_metrics in sorted(act_breakdown.items()):
        print(
            f"  {slug:<40} sca={act_metrics['section_citation_accuracy']:.3f}"
            f"  da={act_metrics['decline_accuracy']:.3f}"
            f"  n={int(act_metrics['count'])}"
        )

    print(divider)
    print("  PER-LANGUAGE BREAKDOWN")
    print(divider)
    lang_breakdown = _breakdown_by_language(pairs)
    for lang, lang_metrics in sorted(lang_breakdown.items()):
        print(
            f"  {lang:<6} sca={lang_metrics['section_citation_accuracy']:.3f}"
            f"  lra={lang_metrics['language_routing_accuracy']:.3f}"
            f"  da={lang_metrics['decline_accuracy']:.3f}"
            f"  n={int(lang_metrics['count'])}"
        )

    print(divider)
    passed = check_thresholds(metrics)
    status_label = "ALL THRESHOLDS PASSED" if passed else "THRESHOLD FAILURE — CI GATE BLOCKED"
    print(f"  {status_label}")
    print(f"{divider}\n")


def main() -> None:
    """Entry point for ``python -m eval.harness``.

    Exits 0 when all threshold metrics pass, 1 when any metric fails.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()

    retrieval_config: dict[str, Any] = {
        "retrieval_top_k": settings.retrieval_top_k,
        "retrieval_top_n": settings.retrieval_top_n,
        "rrf_k": settings.rrf_k,
        "vector_weight": settings.vector_weight,
        "lexical_weight": settings.lexical_weight,
        "similarity_threshold": settings.similarity_threshold,
        "cross_lingual_floor": settings.cross_lingual_floor,
    }

    pairs, metrics = asyncio.run(_run_harness(settings))

    run_path = persist_run(
        metrics=metrics,
        record_count=len(pairs),
        prompt_version="v1",
        retrieval_config=retrieval_config,
        reranker_version=settings.rerank_model,
    )

    _print_report(metrics, pairs, settings, run_path)

    passed = check_thresholds(metrics)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
