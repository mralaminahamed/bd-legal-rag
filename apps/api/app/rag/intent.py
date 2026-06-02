"""Query intent classifier for routing to the correct generation pipeline.

Intents:
- ``legal_qa``      — Specific question about what the law says (existing behavior).
- ``legal_advice``  — Advice-seeking: "should I", "can I sue", "what do I do if…".
- ``act_summary``   — Summarise what an act covers: "summarize the Labour Act".
- ``section_list``  — List sections/chapters: "list sections of Companies Act".
- ``act_explain``   — Explain scope/purpose: "what does the DSA cover?", "tell me about X".

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re
from typing import Literal

QueryIntent = Literal["legal_qa", "legal_advice", "act_summary", "section_list", "act_explain"]

# ── Section list patterns ─────────────────────────────────────────────────────
_LIST_EN = re.compile(
    r"\b(?:list|show|give me|what are the|enumerate)\b.{0,30}"
    r"(?:sections?|chapters?|parts?|provisions?|clauses?)\b",
    re.IGNORECASE,
)
_LIST_BN = re.compile(
    r"(?:ধারাগুলো|ধারাসমূহ|অধ্যায়গুলো|তালিকা|তালিকাভুক্ত|কোন কোন ধারা|কতটি ধারা)"
)

# ── Summary patterns ──────────────────────────────────────────────────────────
_SUMMARY_EN = re.compile(
    r"\b(?:summarize?|summarise?|summary|overview|brief(?:ly)?|outline|"
    r"in\s+brief|give\s+me\s+(?:a\s+)?(?:brief|short|quick|overview))\b",
    re.IGNORECASE,
)
_SUMMARY_BN = re.compile(
    r"(?:সারসংক্ষেপ|সংক্ষেপ|সংক্ষিপ্ত|সংক্ষিপ্তসার|সামারি|ওভারভিউ)"
)

# ── Explain patterns ──────────────────────────────────────────────────────────
_EXPLAIN_EN = re.compile(
    r"\b(?:explain|tell me about|what (?:is|does|covers?|contains?|includes?|are)"
    r"(?:\s+the)?|about the|describe|introduction to|purpose of|scope of)\b",
    re.IGNORECASE,
)
_EXPLAIN_BN = re.compile(
    r"(?:ব্যাখ্যা|বর্ণনা|সম্পর্কে বলুন|কী বিষয়ে|কিসের|উদ্দেশ্য|পরিচিতি|বিস্তারিত বলুন)"
)

# ── Legal advice patterns ─────────────────────────────────────────────────────
_ADVICE_EN = re.compile(
    r"\b(?:should\s+i|can\s+i|am\s+i\s+(?:allowed|entitled|liable|required)|"
    r"what\s+(?:should|can|must|do)\s+i|how\s+(?:do|can|should)\s+i|"
    r"is\s+it\s+legal\s+for\s+(?:me|us)|advise\s+me|my\s+rights|"
    r"what\s+are\s+my|do\s+i\s+have\s+to|can\s+(?:they|he|she|my\s+employer))\b",
    re.IGNORECASE,
)
_ADVICE_BN = re.compile(
    r"(?:আমার\s+কি|আমি\s+কি\s+(?:করব|পারি|পারব)|কী\s+করা\s+উচিত|"
    r"আমাকে\s+কি\s+করতে\s+হবে|আমার\s+অধিকার|পরামর্শ\s+দিন|আমার\s+ক্ষেত্রে)"
)


def classify(query: str) -> QueryIntent:
    """Classify *query* into one of five intents.

    Evaluated in priority order: section_list → summary → explain → advice → qa.

    Args:
        query: Raw user query string (BN, EN, or mixed).

    Returns:
        QueryIntent: The most likely intent.
    """
    if _LIST_EN.search(query) or _LIST_BN.search(query):
        return "section_list"
    if _SUMMARY_EN.search(query) or _SUMMARY_BN.search(query):
        return "act_summary"
    if _EXPLAIN_EN.search(query) or _EXPLAIN_BN.search(query):
        return "act_explain"
    if _ADVICE_EN.search(query) or _ADVICE_BN.search(query):
        return "legal_advice"
    return "legal_qa"
