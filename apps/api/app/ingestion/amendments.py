"""Amendment annotation detection for bdlaws provision pages.

Parses the inline amendment markers that bdlaws embeds within provision HTML
(e.g. ``"Substituted by Act No. XLII of 2006"`` or ``"Inserted by …"``) and
returns structured :class:`AmendmentInfo` objects. Where no annotation is found
the provision is recorded with ``effective_from = fetched_at`` and
``provenance = "snapshot"`` so users understand the temporal coverage limit
(architecture §2.2, ADR-006).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

# Amendment action verbs found in bdlaws annotation text.
_ACTION_RE = re.compile(
    r"\b(substituted|inserted|added|omitted|replaced|amended|deleted)\b",
    re.IGNORECASE,
)
# Act reference patterns: "Act No. X of YYYY" or "Act XLII of 2006".
_ACT_REF_RE = re.compile(
    r"Act(?:\s+No\.?)?\s+([A-Z0-9]+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)
# Standalone four-digit year (fallback).
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
# Amendment marker class names used by bdlaws.
_AMENDMENT_SELECTORS = [
    ".amendment",
    ".amend",
    "[class*='amend']",
    "[class*='insert']",
    "[class*='substitut']",
    "[class*='footnote']",
    ".footnote",
    ".endnote",
]


@dataclass(frozen=True)
class AmendmentInfo:
    """Structured amendment annotation for one provision revision.

    Attributes:
        effective_from: Date from which this revision is in force.
        effective_to: Date until which this revision was in force; ``None``
            if it is the current version.
        amending_act_slug: Slug of the Act that introduced this revision, if
            the annotation supplies enough information to resolve it; ``None``
            otherwise.
        provenance: ``"annotated"`` when the date comes from a portal annotation;
            ``"snapshot"`` when it defaults to the crawl date.
        raw_annotation: The raw annotation text, for audit / debugging.
    """

    effective_from: date
    effective_to: date | None
    amending_act_slug: str | None
    provenance: Literal["annotated", "snapshot"]
    raw_annotation: str


def _parse_year(text: str) -> int | None:
    """Extract the first four-digit year token from text.

    Args:
        text: Annotation text to search.

    Returns:
        int | None: The year, or ``None`` if not found.
    """
    m = _YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def _act_slug_from_annotation(text: str) -> str | None:
    """Attempt to derive an Act slug from an amendment annotation string.

    Extracts the Act number and year (e.g. ``"Act XLII of 2006"``) and builds
    a slug in the form used by our ``config/acts/*.yaml`` files.  Returns
    ``None`` when the reference is too vague to resolve.

    Args:
        text: Raw annotation text.

    Returns:
        str | None: A slug candidate (e.g. ``"labour-act-2006"``), or ``None``.
    """
    m = _ACT_REF_RE.search(text)
    if m:
        year = m.group(2)
        # Produce a minimal slug; the registry will reconcile with real slugs.
        return f"act-{year}"
    return None


def detect_amendments(html: str, fetched_at: datetime) -> list[AmendmentInfo]:
    """Detect amendment annotations in an HTML fragment.

    Searches for known bdlaws annotation patterns. When annotations are found
    each is returned as an ``"annotated"`` :class:`AmendmentInfo`. When none
    are found a single ``"snapshot"`` entry is returned using ``fetched_at``
    as ``effective_from`` so the temporal coverage limit is explicit.

    Args:
        html: HTML of the provision or full page to scan.
        fetched_at: The crawl timestamp; used as the fallback effective date.

    Returns:
        list[AmendmentInfo]: At least one entry per call.
    """
    tree = HTMLParser(html)
    annotations: list[str] = []

    for selector in _AMENDMENT_SELECTORS:
        for node in tree.css(selector):
            text = node.text(deep=True).strip()
            if text and _ACTION_RE.search(text):
                annotations.append(text)

    if not annotations:
        return [
            AmendmentInfo(
                effective_from=fetched_at.date(),
                effective_to=None,
                amending_act_slug=None,
                provenance="snapshot",
                raw_annotation="",
            )
        ]

    results: list[AmendmentInfo] = []
    for annotation in annotations:
        year = _parse_year(annotation)
        effective_from = date(year, 1, 1) if year else fetched_at.date()
        amending_slug = _act_slug_from_annotation(annotation)
        results.append(
            AmendmentInfo(
                effective_from=effective_from,
                effective_to=None,
                amending_act_slug=amending_slug,
                provenance="annotated",
                raw_annotation=annotation[:500],
            )
        )

    logger.debug(
        "amendment annotations detected",
        extra={"count": len(results)},
    )
    return results


def latest_amendment(html: str, fetched_at: datetime) -> AmendmentInfo:
    """Return the most recent amendment annotation from an HTML fragment.

    When multiple annotations are present, the one with the latest
    ``effective_from`` date is returned. When none are present, the snapshot
    fallback is returned.

    Args:
        html: HTML to scan.
        fetched_at: Crawl timestamp used as the fallback effective date.

    Returns:
        AmendmentInfo: The most recent amendment, or the snapshot fallback.
    """
    all_amendments = detect_amendments(html, fetched_at)
    return max(all_amendments, key=lambda a: a.effective_from)
