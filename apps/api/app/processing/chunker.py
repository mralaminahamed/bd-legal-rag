"""Section-hierarchy-aware chunker (FR-PR-1, FR-PR-2, architecture §2.3).

Converts provision revision text into ChunkSpec objects. Each chunk text is
prefixed with the statutory hierarchy path so the embedding captures the
provision's position in the Act's structure, materially improving retrieval
precision (architecture §2.3).

Oversized provisions are split at paragraph boundaries with configurable overlap.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings

_PARAGRAPH_SEP = re.compile(r"\n{2,}")


@dataclass(frozen=True)
class ChunkSpec:
    """One chunk derived from a provision revision.

    Attributes:
        content: Chunk text prefixed with ``hierarchy_path`` and a newline.
            This is what gets embedded.
        hierarchy_path: Statutory breadcrumb stored as its own DB column.
        chunk_index: Zero-based position of this chunk within its revision.
        token_count: Approximate token count of ``content``.
    """

    content: str
    hierarchy_path: str
    chunk_index: int
    token_count: int


def _count_tokens(text: str) -> int:
    """Approximate BPE token count via a character-based heuristic.

    One token ≈ 4 characters for Latin scripts. Bengali is more info-dense per
    character, so this estimate is conservative (over-estimates), which prevents
    creating chunks that exceed the embedder's per-text limit.

    Args:
        text: Text to measure.

    Returns:
        int: Estimated token count, always ≥ 1.
    """
    return max(1, len(text) // 4)


def _tail_chars(text: str, token_limit: int) -> str:
    """Return the trailing portion of text up to approximately token_limit tokens.

    Used to seed the overlap prefix for the next chunk.

    Args:
        text: Source text.
        token_limit: Desired maximum token count of the returned tail.

    Returns:
        str: Trailing substring of text.
    """
    char_limit = token_limit * 4
    return text[-char_limit:] if len(text) > char_limit else text


def _split_at_paragraphs(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Split text at blank lines with overlap, keeping segments under max_tokens.

    Algorithm:
    1. Split on two or more consecutive newlines (paragraph breaks).
    2. Accumulate paragraphs greedily until adding the next would exceed max_tokens.
    3. On overflow, flush the segment (prepending overlap tail from previous) and
       start fresh with the overlap tail as prefix.
    4. A single paragraph exceeding max_tokens is split at single newlines;
       if still too large, taken as-is (embedder truncates preserving the
       hierarchy_path prefix at the start).

    Args:
        text: Provision text to split.
        max_tokens: Maximum approximate tokens per output segment.
        overlap_tokens: Approximate token count to carry as overlap.

    Returns:
        list[str]: Non-empty text segments.
    """
    raw_paras = _PARAGRAPH_SEP.split(text.strip())

    paragraphs: list[str] = []
    for para in raw_paras:
        if not para.strip():
            continue
        if _count_tokens(para) > max_tokens:
            sub = [p.strip() for p in para.split("\n") if p.strip()]
            if all(_count_tokens(p) <= max_tokens for p in sub):
                paragraphs.extend(sub)
                continue
        paragraphs.append(para.strip())

    if not paragraphs:
        return [text.strip()]

    segments: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0
    overlap_prefix = ""

    for para in paragraphs:
        para_tokens = _count_tokens(para)
        if current_tokens + para_tokens > max_tokens and current_parts:
            body = "\n\n".join(current_parts)
            seg = (overlap_prefix + "\n" + body).strip() if overlap_prefix else body
            segments.append(seg)
            overlap_prefix = _tail_chars(body, overlap_tokens)
            current_parts = []
            current_tokens = 0
        current_parts.append(para)
        current_tokens += para_tokens

    if current_parts:
        body = "\n\n".join(current_parts)
        seg = (overlap_prefix + "\n" + body).strip() if overlap_prefix else body
        segments.append(seg)

    return segments or [text.strip()]


def chunk_provision(
    text: str,
    hierarchy_path: str,
    settings: Settings,
) -> list[ChunkSpec]:
    """Produce one or more ChunkSpec objects from a provision revision.

    Each returned chunk's content is hierarchy_path followed by a newline and the
    chunk body. A provision fitting within chunk_max_tokens yields exactly one chunk;
    an oversized provision is split at paragraph boundaries with chunk_overlap_tokens
    of overlap (FR-PR-1, architecture §2.3).

    Empty provisions produce an empty list; the caller must skip writing chunks.

    Args:
        text: Verbatim provision text (normalised, Bengali characters preserved).
        hierarchy_path: Statutory breadcrumb string, e.g.
            "Bangladesh Labour Act, 2006 > Chapter X > Section 103 (Weekly holiday)".
        settings: Application settings supplying token-limit tunables.

    Returns:
        list[ChunkSpec]: Zero or more ChunkSpec objects, indexed from zero.
    """
    stripped = text.strip()
    if not stripped:
        return []

    content = f"{hierarchy_path}\n{stripped}"
    if _count_tokens(content) <= settings.chunk_max_tokens:
        return [
            ChunkSpec(
                content=content,
                hierarchy_path=hierarchy_path,
                chunk_index=0,
                token_count=_count_tokens(content),
            )
        ]

    path_tokens = _count_tokens(hierarchy_path) + 1  # +1 for the "\n" separator
    text_budget = max(1, settings.chunk_max_tokens - path_tokens)
    segments = _split_at_paragraphs(
        stripped,
        text_budget,
        settings.chunk_overlap_tokens,
    )
    return [
        ChunkSpec(
            content=f"{hierarchy_path}\n{seg}",
            hierarchy_path=hierarchy_path,
            chunk_index=idx,
            token_count=_count_tokens(f"{hierarchy_path}\n{seg}"),
        )
        for idx, seg in enumerate(segments)
    ]
