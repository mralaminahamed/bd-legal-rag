"""Bengali Unicode-block language router (FR-QR-2, architecture §2.4).

Detects query language from script composition — no third-party model.
Bengali Unicode block U+0980–U+09FF coverage drives the classification.
Mixed-script queries receive a heuristic confidence score.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from typing import Literal

_BN_LO = 0x0980
_BN_HI = 0x09FF

LanguageCode = Literal["bn", "en", "mixed"]

_BN_MAJORITY = 0.70
_EN_MAJORITY = 0.10


def detect_language(text: str) -> tuple[LanguageCode, float]:
    """Detect the dominant language of text using Unicode-block analysis.

    Counts characters in the Bengali Unicode block (U+0980–U+09FF) as a
    fraction of all non-whitespace characters. Heuristic thresholds:

    - coverage ≥ 0.70 → ``"bn"``  with confidence = coverage ratio
    - coverage ≤ 0.10 → ``"en"``  with confidence = 1 − coverage ratio
    - otherwise       → ``"mixed"`` with confidence = max(ratio, 1 − ratio)

    No third-party model is used (FR-QR-2).

    Args:
        text: The raw query string.

    Returns:
        tuple[LanguageCode, float]: ``(language_code, confidence)`` where
            confidence ∈ [0, 1].
    """
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return "en", 1.0

    bn_count = sum(1 for c in non_ws if _BN_LO <= ord(c) <= _BN_HI)
    ratio = bn_count / len(non_ws)

    if ratio >= _BN_MAJORITY:
        return "bn", ratio
    if ratio <= _EN_MAJORITY:
        return "en", 1.0 - ratio
    return "mixed", max(ratio, 1.0 - ratio)
