"""Provision text normalisation.

Converts the raw HTML fetched from bdlaws into clean plain text suitable for
chunking and embedding. Critically, no Unicode normalisation (NFKC/NFC/NFD) is
applied: Bengali combining marks must survive bit-for-bit so that retrieval and
citation matching work correctly (NFR-SC-4 commentary).

Executable markup (``<script>``, ``<style>``, etc.) is stripped structurally
via selectolax — only text nodes survive so tags, attributes, and inline
handlers cannot reach storage (NFR-SC-4).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# Tags whose entire subtree is discarded — never user-visible content.
_DROP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "head",
        "iframe",
        "object",
        "embed",
        "svg",
        "meta",
        "link",
    }
)

_MULTISPACE = re.compile(r"[ \t]+")
_MULTINEWLINE = re.compile(r"\n{3,}")


def extract_text(html: str) -> str:
    """Extract clean plain text from an HTML fragment, preserving Bengali.

    Uses selectolax to walk the DOM structurally. Drop-element subtrees are
    removed before text extraction so no executable markup text can survive.
    No Unicode normalisation is applied — Bengali combining marks are preserved
    bit-for-bit.

    Args:
        html: Raw HTML string (full page or fragment).

    Returns:
        str: Clean, whitespace-normalised plain text with no HTML markup.
    """
    tree = HTMLParser(html)

    # Remove entire subtrees for executable/non-visible elements.
    for tag in _DROP_TAGS:
        for node in tree.css(tag):
            node.decompose()

    raw = tree.body.text(deep=True, separator="\n") if tree.body else tree.text(deep=True)
    return _clean_whitespace(raw)


def clean_provision_text(text: str) -> str:
    """Normalise whitespace in a provision text string without altering Unicode.

    Does NOT call ``unicodedata.normalize()`` — Bengali combining marks must be
    preserved exactly as they appear on the bdlaws portal.

    Args:
        text: Raw provision text (may contain excess whitespace).

    Returns:
        str: Whitespace-normalised text with trimmed lines.
    """
    return _clean_whitespace(text)


def _clean_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs and reduce blank lines to at most one.

    Bengali characters are left completely untouched; only ASCII whitespace
    codepoints are manipulated.

    Args:
        text: Text with possible excess whitespace.

    Returns:
        str: Cleaned text.
    """
    lines = [_MULTISPACE.sub(" ", line).strip() for line in text.splitlines()]
    joined = "\n".join(lines)
    return _MULTINEWLINE.sub("\n\n", joined).strip()
