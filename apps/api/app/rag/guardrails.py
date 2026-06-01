"""Versioned bilingual normative-phrase guardrails (architecture §2.5).

``scan()`` detects normative conclusions in generated text.  On violation,
the generator retries once with a stricter system prompt; a second violation
triggers fail-open.  The retry/fail-open logic lives in ``generator.py``;
this module only detects.

EN blacklist: "you must", "you cannot", "it is illegal", "you are required to".
BN blacklist: "আপনাকে অবশ্যই", "আপনি পারবেন না", "এটি অবৈধ", "আপনাকে করতে হবে".

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re

_EN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("you must", re.compile(r"\byou\s+must\b", re.IGNORECASE)),
    ("you cannot", re.compile(r"\byou\s+can(?:not|'t)\b", re.IGNORECASE)),
    ("it is illegal", re.compile(r"\bit\s+is\s+illegal\b", re.IGNORECASE)),
    ("you are required to", re.compile(r"\byou\s+are\s+required\s+to\b", re.IGNORECASE)),
    ("you need to", re.compile(r"\byou\s+need\s+to\b", re.IGNORECASE)),
    ("you must not", re.compile(r"\byou\s+must\s+not\b", re.IGNORECASE)),
]

_BN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("আপনাকে অবশ্যই", re.compile(r"আপনাকে\s+অবশ্যই")),
    ("আপনি পারবেন না", re.compile(r"আপনি\s+পারবেন\s+না")),
    ("এটি অবৈধ", re.compile(r"এটি\s+অবৈধ")),
    ("আপনাকে করতে হবে", re.compile(r"আপনাকে\s+করতে\s+হবে")),
    ("আপনি পারেন না", re.compile(r"আপনি\s+পারেন\s+না")),
]

_ALL_PATTERNS: list[tuple[str, re.Pattern[str]]] = _EN_PATTERNS + _BN_PATTERNS


def scan(text: str) -> str | None:
    """Scan *text* for normative-conclusion phrases.

    Args:
        text: LLM-generated response text.

    Returns:
        str | None: The first matched phrase label if a violation is found,
            ``None`` if the text is clean.
    """
    for label, pattern in _ALL_PATTERNS:
        if pattern.search(text):
            return label
    return None
