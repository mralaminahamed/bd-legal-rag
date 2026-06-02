"""Canonical bilingual citation formatter (ADR-005, architecture §2.5).

This is the ONLY module that formats citation strings.  Citation placeholders
emitted by the LLM (``{{cite:chunk_id}}``) are resolved post-generation.
Unrecognised chunk_ids are stripped — the LLM is never trusted to self-cite.

Bengali numerals (০–৯) are used for all numeric elements in Bengali citations.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BN_DIGIT_TABLE = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
# Match both {cite:id} (model output) and {{cite:id}} (legacy double-brace format)
_PLACEHOLDER_RE = re.compile(r"\{\{cite:([^}]+)\}\}|\{cite:([^}]+)\}")


@dataclass(frozen=True)
class CitationContext:
    """Metadata needed to format one citation.

    Attributes:
        chunk_id: Chunk identifier (matches LLM-emitted placeholder).
        act_name_en: Official English act title.
        act_name_bn: Official Bengali act title.
        act_year: Year of enactment.
        section_ref: Section reference string (e.g. ``103(1)(a)``).
        source_url: Canonical bdlaws URL for this provision.
    """

    chunk_id: str
    act_name_en: str
    act_name_bn: str
    act_year: int
    section_ref: str
    source_url: str


def to_bn_numerals(text: str) -> str:
    """Convert ASCII digits in *text* to Bengali numerals.

    Non-digit characters (letters, punctuation) are preserved.

    Args:
        text: Input string possibly containing ASCII digits.

    Returns:
        str: The string with digits converted to Bengali numerals (০–৯).
    """
    return text.translate(_BN_DIGIT_TABLE)


def format_citation(ctx: CitationContext, *, language: str) -> str:
    """Format a single citation in the requested language.

    English form:  ``Section X(Y)(Z) of <Act Name>, <Year>``
    Bengali form:  ``<আইনের নাম>, <বছর>-এর ধারা X(Y)(Z)``

    Bengali numerals (০–৯) are used for all digit sequences in Bengali output.

    Args:
        ctx: Citation context with act and section metadata.
        language: ``bn`` for Bengali, any other value for English.

    Returns:
        str: The formatted citation string.
    """
    if language == "bn":
        bn_year = to_bn_numerals(str(ctx.act_year))
        bn_section = to_bn_numerals(ctx.section_ref)
        text = f"{ctx.act_name_bn}, {bn_year}-এর ধারা {bn_section}"
    else:
        text = f"Section {ctx.section_ref} of {ctx.act_name_en}, {ctx.act_year}"
    if ctx.source_url:
        return f"[{text}]({ctx.source_url})"
    return text


def resolve_placeholders(
    text: str,
    *,
    contexts: dict[str, CitationContext],
    language: str,
) -> str:
    """Replace ``{{cite:chunk_id}}`` placeholders with canonical citation strings.

    Placeholders whose ``chunk_id`` is not in *contexts* are silently stripped
    (not left as-is and not fabricated).  Only supplied chunk_ids are rendered.

    Args:
        text: LLM-generated text containing zero or more placeholders.
        contexts: Mapping from chunk_id string to :class:`CitationContext`.
        language: Response language (``bn`` or ``en``).

    Returns:
        str: Text with all placeholders resolved or stripped.
    """

    def _replace(m: re.Match[str]) -> str:
        # group(1) = double-brace match, group(2) = single-brace match
        chunk_id = m.group(1) or m.group(2)
        ctx = contexts.get(chunk_id)
        if ctx is None:
            return ""
        return format_citation(ctx, language=language)

    return _PLACEHOLDER_RE.sub(_replace, text)
