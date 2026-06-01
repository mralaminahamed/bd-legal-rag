"""Generation pipeline (architecture §2.5, FR-GN-1..12, NFR-LS-1..5).

Orchestrates the fixed generation sequence:

    cache.get
      → decline_gate.classify
          → if decline → decline_response ──┐
      → circuit_breaker.guard               │
      → provider.complete / .stream         │
          → on ProviderUnavailable → fail-open
      → citation.resolve_placeholders       │
      → guardrails.scan                     │
          → on violation: retry once        │
      → disclaimer.inject ◀────────────────┘
      → cache.set

``disclaimer.inject`` runs on EVERY path: normal, decline, cache-hit,
fail-open, and guardrails-fail-open.  This is the only module that calls it.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Act
from app.llm import factory as llm_factory
from app.llm.base import CompletionRequest, ProviderUnavailable, TokenUsage
from app.llm.cache import ResponseCache, cache_key
from app.llm.circuit_breaker import CostCeilingExceeded, guard
from app.prompts import registry as prompt_registry
from app.prompts.safety import decline as decline_mod
from app.prompts.safety import disclaimer as disclaimer_mod
from app.rag.citation import CitationContext, format_citation, resolve_placeholders
from app.rag.decline_gate import classify as decline_classify
from app.rag.guardrails import scan as guardrails_scan
from app.rag.retriever import RetrievedChunk
from app.rag.service import RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """A single event in a streaming generation response.

    Attributes:
        type: ``token`` for a text delta; ``final`` for the completed result.
        text: Text delta for ``token`` events; empty for ``final``.
        answer: Full validated answer (``final`` events only).
        citations: Resolved citation strings (``final`` events only).
        disclaimer: Active disclaimer text (``final`` events only).
        cached: ``True`` if the result came from the response cache.
        degraded: ``True`` if the LLM or circuit breaker caused a fail-open.
        declined: ``True`` if the decline gate fired.
        usage: Token usage (``final`` events only; ``None`` on cache-hit/decline).
    """

    type: str
    text: str
    answer: str | None
    citations: list[str] | None
    disclaimer: str | None
    cached: bool
    degraded: bool
    declined: bool
    usage: Any | None


@dataclass
class GenerateResponse:
    """Full (non-streaming) generation result.

    Attributes:
        answer: Validated, disclaimer-bearing answer text.
        citations: Resolved citation strings for the supplied chunks.
        disclaimer: The active disclaimer text (also embedded in ``answer``).
        cached: ``True`` if the result came from the response cache.
        degraded: ``True`` if the LLM or circuit breaker caused a fail-open.
        declined: ``True`` if the decline gate fired.
        usage: Token usage (``None`` on cache-hit, decline, or fail-open).
        disclaimer_version: The disclaimer version string logged with this response.
    """

    answer: str
    citations: list[str]
    disclaimer: str
    cached: bool
    degraded: bool
    declined: bool
    usage: Any | None
    disclaimer_version: str


# ── Private helpers ────────────────────────────────────────────────────────────

async def _resolve_act_metadata(
    session: AsyncSession,
    act_ids: set[str],
) -> dict[str, Act]:
    """Fetch act metadata rows needed for citation formatting.

    Args:
        session: Async database session.
        act_ids: Set of act UUID strings to resolve.

    Returns:
        dict[str, Act]: Mapping from act_id string to Act ORM row.
    """
    if not act_ids:
        return {}
    result = await session.execute(
        select(Act).where(Act.id.in_([uuid.UUID(aid) for aid in act_ids]))
    )
    rows = result.scalars().all()
    return {str(row.id): row for row in rows}


def _build_citation_contexts(
    chunks: list[RetrievedChunk],
    act_map: dict[str, Act],
) -> dict[str, CitationContext]:
    """Build citation contexts from chunks and resolved act metadata.

    Args:
        chunks: Retrieved chunks.
        act_map: Act metadata from the database.

    Returns:
        dict[str, CitationContext]: Mapping from chunk_id string to context.
    """
    contexts: dict[str, CitationContext] = {}
    for chunk in chunks:
        act = act_map.get(str(chunk.act_id))
        if act is None:
            continue
        path_parts = chunk.hierarchy_path.split(" > ")
        section_ref = path_parts[-1] if path_parts else str(chunk.chunk_id)[:8]
        contexts[str(chunk.chunk_id)] = CitationContext(
            chunk_id=str(chunk.chunk_id),
            act_name_en=act.full_name_en,
            act_name_bn=act.full_name_bn,
            act_year=act.act_year,
            section_ref=section_ref,
        )
    return contexts


def _estimate_input_tokens(system: str, user: str) -> int:
    """Rough token estimate (1 token ≈ 4 chars).

    Args:
        system: System prompt text.
        user: User message text.

    Returns:
        int: Estimated input token count.
    """
    return (len(system) + len(user)) // 4


def _build_failopen_answer(
    chunks: list[RetrievedChunk],
    contexts: dict[str, CitationContext],
    language: str,
) -> str:
    """Build a fail-open response from raw provisions and citations.

    Args:
        chunks: Retrieved chunks to surface verbatim.
        contexts: Citation contexts for inline citation strings.
        language: Response language (``bn`` or ``en``).

    Returns:
        str: Provision text with inline citations, no LLM summary.
    """
    lines: list[str] = ["Relevant provisions (no summary available):"]
    for chunk in chunks:
        citation = ""
        ctx = contexts.get(str(chunk.chunk_id))
        if ctx:
            citation = f" [{format_citation(ctx, language=language)}]"
        lines.append(f"\n{chunk.content}{citation}")
    return "\n".join(lines)


def _resolve_model_name(s: Settings) -> str:
    """Return the active model name from settings.

    Args:
        s: Application settings.

    Returns:
        str: Model identifier string.
    """
    if s.default_provider == "anthropic":
        return s.anthropic_model
    if s.default_provider == "openai":
        return s.openai_model
    return s.ollama_model


def _get_cache(s: Settings) -> ResponseCache | None:
    """Return a ResponseCache if Redis is available, else None.

    Args:
        s: Application settings.

    Returns:
        ResponseCache | None: Cache instance or ``None`` if Redis unavailable.
    """
    try:
        from app.db.redis import get_redis

        return ResponseCache(redis=get_redis(), ttl_seconds=s.response_cache_ttl_seconds)
    except Exception:
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

async def generate(
    *,
    retrieval_result: RetrievalResult,
    session: AsyncSession,
    settings: Settings,
) -> GenerateResponse:
    """Execute the fixed generation pipeline and return a full response.

    Pipeline:
        cache.get → decline_gate.classify → circuit_breaker.guard
        → provider.complete → citation.resolve_placeholders
        → guardrails.scan (retry once on violation)
        → disclaimer.inject → cache.set

    The disclaimer is injected on EVERY path including cache-hit, decline,
    and fail-open (NFR-LS-1).

    Args:
        retrieval_result: Output from the retrieval pipeline.
        session: Async database session for act metadata resolution.
        settings: Application settings.

    Returns:
        GenerateResponse: Validated, disclaimer-bearing response.
    """
    s = settings
    language = retrieval_result.detected_language
    if language == "mixed":
        language = "en"

    prompt_family = "legal_answer"
    prompt_version = "v1"
    disclaimer_version = s.active_disclaimer_version
    decline_version = s.active_decline_version
    reranker_version = s.rerank_model

    disclaimer_obj = disclaimer_mod.resolve(disclaimer_version)
    disc = disclaimer_obj.bn if language == "bn" else disclaimer_obj.en

    # ── 1. Decline gate (early — before any DB or LLM work) ───────────────────
    decline_decision = decline_classify(
        retrieval_result.query,
        chunks=retrieval_result.chunks,
        settings=s,
    )
    if decline_decision.declined:
        decline_text_obj = decline_mod.resolve(decline_version)
        decline_body = decline_text_obj.bn if language == "bn" else decline_text_obj.en
        answer = disclaimer_mod.inject(decline_body, version=disclaimer_version, language=language)
        return GenerateResponse(
            answer=answer,
            citations=[],
            disclaimer=disc,
            cached=False,
            degraded=False,
            declined=True,
            usage=None,
            disclaimer_version=disclaimer_version,
        )

    # ── Resolve act metadata and citation contexts ────────────────────────────
    act_ids = {str(c.act_id) for c in retrieval_result.chunks}
    act_map = await _resolve_act_metadata(session, act_ids)
    contexts = _build_citation_contexts(retrieval_result.chunks, act_map)

    prompt_mod = prompt_registry.resolve(prompt_family, prompt_version)
    rendered = prompt_mod.render(
        question=retrieval_result.query,
        chunks=retrieval_result.chunks,
        language=language,
    )
    chunk_ids = [str(c.chunk_id) for c in retrieval_result.chunks]
    key = cache_key(
        query=retrieval_result.query,
        chunk_ids=chunk_ids,
        as_of_date=str(retrieval_result.as_of_date),
        model=_resolve_model_name(s),
        prompt_version=prompt_version,
        reranker_version=reranker_version,
    )

    # ── 2. Cache check ────────────────────────────────────────────────────────
    cache = _get_cache(s)
    if cache:
        cached_text = await cache.get(key)
        if cached_text is not None:
            if not cached_text.endswith(disc):
                base = (
                    cached_text.rsplit("\n\n", 1)[0]
                    if "\n\n" in cached_text
                    else cached_text
                )
                cached_text = disclaimer_mod.inject(
                    base, version=disclaimer_version, language=language
                )
            return GenerateResponse(
                answer=cached_text,
                citations=list(contexts.keys()),
                disclaimer=disc,
                cached=True,
                degraded=False,
                declined=False,
                usage=None,
                disclaimer_version=disclaimer_version,
            )

    # ── 3. Circuit breaker (after decline check, before provider call) ────────
    input_tokens = _estimate_input_tokens(rendered.system, rendered.user)
    try:
        guard(
            input_tokens,
            cost_per_1k_input=s.cost_per_1k_input_usd,
            cost_per_1k_output=s.cost_per_1k_output_usd,
            max_output_tokens=s.llm_max_output_tokens,
            ceiling=s.cost_ceiling_usd_per_request,
        )
    except CostCeilingExceeded as exc:
        logger.warning(
            "cost_ceiling_exceeded projected=%.4f ceiling=%.4f",
            exc.projected_cost,
            exc.ceiling,
        )
        fail_body = _build_failopen_answer(retrieval_result.chunks, contexts, language)
        answer = disclaimer_mod.inject(fail_body, version=disclaimer_version, language=language)
        return GenerateResponse(
            answer=answer,
            citations=list(contexts.keys()),
            disclaimer=disc,
            cached=False,
            degraded=True,
            declined=False,
            usage=None,
            disclaimer_version=disclaimer_version,
        )

    # ── 4. LLM call with guardrails retry ────────────────────────────────────
    provider = llm_factory.create_provider(s)
    request = CompletionRequest(
        system=rendered.system,
        user=rendered.user,
        max_tokens=s.llm_max_output_tokens,
    )
    stricter_system = (
        rendered.system
        + "\n\nSTRICT REMINDER: Do NOT assert legal conclusions in your own voice. "
        "Every normative statement must be attributed to a provision with {{cite:chunk_id}}."
    )

    raw_text: str | None = None
    usage: TokenUsage | None = None
    degraded = False

    for attempt in range(2):
        try:
            if attempt == 1:
                retry_req = CompletionRequest(
                    system=stricter_system,
                    user=rendered.user,
                    max_tokens=s.llm_max_output_tokens,
                )
                result = await provider.complete(retry_req)
            else:
                result = await provider.complete(request)
            raw_text = result.text
            usage = result.usage
        except ProviderUnavailable as exc:
            logger.warning("provider_unavailable: %s", exc)
            degraded = True
            break

        violation = guardrails_scan(raw_text)
        if violation is None:
            break
        logger.warning("guardrails_violation attempt=%d phrase=%r", attempt + 1, violation)
        if attempt == 1:
            degraded = True
            raw_text = None

    # ── 5. Build final answer ─────────────────────────────────────────────────
    if degraded or raw_text is None:
        fail_body = _build_failopen_answer(retrieval_result.chunks, contexts, language)
        answer = disclaimer_mod.inject(fail_body, version=disclaimer_version, language=language)
        return GenerateResponse(
            answer=answer,
            citations=list(contexts.keys()),
            disclaimer=disc,
            cached=False,
            degraded=True,
            declined=False,
            usage=usage,
            disclaimer_version=disclaimer_version,
        )

    resolved = resolve_placeholders(raw_text, contexts=contexts, language=language)
    answer = disclaimer_mod.inject(resolved, version=disclaimer_version, language=language)

    if cache:
        await cache.set(key, answer)

    return GenerateResponse(
        answer=answer,
        citations=list(contexts.keys()),
        disclaimer=disc,
        cached=False,
        degraded=False,
        declined=False,
        usage=usage,
        disclaimer_version=disclaimer_version,
    )


async def generate_stream(
    *,
    retrieval_result: RetrievalResult,
    session: AsyncSession,
    settings: Settings,
) -> AsyncGenerator[StreamEvent, None]:
    """Run the streaming generation pipeline.

    Args:
        retrieval_result: Ranked chunks and metadata from the retrieval service.
        session: Async database session for act-metadata lookups.
        settings: Active application configuration.

    Yields:
        :class:`StreamEvent` instances: ``token`` deltas followed by a ``final`` event.
    """
    raise NotImplementedError("generate_stream() pipeline implemented in Task 3")
    yield StreamEvent(  # makes this an async generator for mypy
        type="",
        text="",
        answer=None,
        citations=None,
        disclaimer=None,
        cached=False,
        degraded=False,
        declined=False,
        usage=None,
    )
