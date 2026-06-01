"""Bilingual advice-seeking decline gate (NFR-LS-3, FR-GN-3).

Declines when:
1. The query matches advice-seeking patterns in EN or BN (even with relevant chunks).
2. Retrieval recall is below the configured floor (no chunks returned).

The LLM is never called when this gate fires.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings
from app.rag.retriever import RetrievedChunk

# English patterns — case-insensitive
_EN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bshould\s+i\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+i\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+(?:we|my|our)\b", re.IGNORECASE),
    re.compile(r"\bis\s+it\s+legal\s+for\s+(?:me|us|him|her|them)\b", re.IGNORECASE),
    re.compile(r"\bcan\s+i\s+(?:sue|file|claim|take)\b", re.IGNORECASE),
    re.compile(r"\bam\s+i\s+(?:allowed|permitted|entitled|liable|required)\b", re.IGNORECASE),
    re.compile(r"\bdo\s+i\s+have\s+(?:to|the right)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:are|is)\s+my\s+(?:rights|options|obligations)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(?:do|can|should)\s+i\b", re.IGNORECASE),
    re.compile(r"\badvise\s+me\b", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+what\s+to\s+do\b", re.IGNORECASE),
]

# Bengali patterns (Unicode-aware, no case folding needed)
_BN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"আমার\s+কি\s+করা\s+উচিত"),
    re.compile(r"আমি\s+কি\s+করব"),
    re.compile(r"আমাকে\s+কি\s+করতে\s+হবে"),
    re.compile(r"আমি\s+কি\s+(?:মামলা|অভিযোগ)\s+করতে\s+পারি"),
    re.compile(r"আমার\s+কি\s+(?:অধিকার|করণীয়)"),
    re.compile(r"আমি\s+কি\s+(?:পারব|পারি)\b"),
    re.compile(r"কী\s+করা\s+উচিত"),
    re.compile(r"কী\s+করব"),
    re.compile(r"পরামর্শ\s+দিন"),
    re.compile(r"আমার\s+ক্ষেত্রে\s+(?:কী|কি)\s+প্রযোজ্য"),
]


@dataclass(frozen=True)
class DeclineDecision:
    """Result from the decline gate.

    Attributes:
        declined: ``True`` when the query must be declined.
        reason: Human-readable reason code (for logging and testing).
    """

    declined: bool
    reason: str


def classify(
    query: str,
    *,
    chunks: list[RetrievedChunk],
    settings: Settings,
) -> DeclineDecision:
    """Classify a query and decide whether to decline.

    Fires on advice-seeking patterns (BN + EN) regardless of retrieved chunk
    quality, and on retrieval recall below the configured floor.

    Args:
        query: The raw user query string.
        chunks: Retrieved chunks from the retrieval pipeline.
        settings: Application settings (recall floor, advice confidence floor).

    Returns:
        DeclineDecision: Whether to decline and the reason.
    """
    # Recall floor check — decline if no chunks retrieved
    if len(chunks) == 0:
        return DeclineDecision(declined=True, reason="recall_floor: no chunks retrieved")

    # Advice-seeking pattern check (EN)
    for pattern in _EN_PATTERNS:
        if pattern.search(query):
            return DeclineDecision(
                declined=True,
                reason=f"advice_seeking_en: matched {pattern.pattern!r}",
            )

    # Advice-seeking pattern check (BN)
    for pattern in _BN_PATTERNS:
        if pattern.search(query):
            return DeclineDecision(
                declined=True,
                reason=f"advice_seeking_bn: matched {pattern.pattern!r}",
            )

    return DeclineDecision(declined=False, reason="")
