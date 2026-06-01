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

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.rag.service import RetrievalResult


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


async def generate(
    *,
    retrieval_result: RetrievalResult,
    session: AsyncSession,
    settings: Settings,
) -> GenerateResponse:
    """Run the full (non-streaming) generation pipeline.

    Args:
        retrieval_result: Ranked chunks and metadata from the retrieval service.
        session: Async database session for act-metadata lookups.
        settings: Active application configuration.

    Returns:
        A :class:`GenerateResponse` with answer, citations, and disclaimer.
    """
    raise NotImplementedError("generate() pipeline implemented in Task 2")


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
    yield StreamEvent(
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
