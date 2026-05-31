"""bdlaws statutory parse tree builder.

Walks the DOM of a bdlaws Act page and emits a :class:`ProvisionNode` tree
matching the architecture spec (``docs/02-Architecture.md`` §2.2). The parser
is *defensive*: it never raises on a missing optional element and records
unrecognised structural patterns as :class:`ParseWarning` objects so they can
be reviewed without aborting ingestion.

The bdlaws portal uses HTML tables and divs for layout. The parser targets the
common structural patterns and falls back gracefully when markup deviates.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from selectolax.parser import HTMLParser, Node

from app.ingestion.normalize import clean_provision_text, extract_text

logger = logging.getLogger(__name__)

_SECTION_NUM_RE = re.compile(r"^(\d+[A-Z]?(?:\.\d+)?)[.\s]")
_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b|\b(\d{4})\b")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ProvisionNode:
    """A node in the statutory parse tree extracted from a bdlaws page.

    Attributes:
        kind: One of ``"act"``, ``"part"``, ``"chapter"``, ``"section"``,
            ``"subsection"``, or ``"clause"``.
        number: Statutory identifier within its parent (e.g. ``"103"``, ``"2"``, ``"a"``).
        title: Optional heading text.
        text: Verbatim provision text; empty string for container nodes.
        children: Ordered child provisions.
        effective_from: Earliest known effective date (``None`` when unknown).
        effective_to: Latest known effective date if superseded (``None`` = current).
        source_url: Canonical URL on the portal.
    """

    kind: Literal["act", "part", "chapter", "section", "subsection", "clause"]
    number: str
    title: str | None
    text: str
    children: tuple[ProvisionNode, ...]
    effective_from: date | None
    effective_to: date | None
    source_url: str


@dataclass
class ParseWarning:
    """A non-fatal warning recorded when the parser encounters unexpected markup.

    Attributes:
        message: Human-readable description of the unexpected pattern.
        context: Optional snippet of the HTML that triggered the warning.
    """

    message: str
    context: str = ""


@dataclass
class ParseResult:
    """The outcome of parsing one bdlaws page.

    Attributes:
        root: The root :class:`ProvisionNode` (kind ``"act"``).
        warnings: Non-fatal parsing warnings for review.
    """

    root: ProvisionNode
    warnings: list[ParseWarning] = field(default_factory=list)


def _norm(text: str) -> str:
    """Collapse whitespace in extracted text without altering Unicode.

    Args:
        text: Raw extracted string.

    Returns:
        str: Single-spaced trimmed string.
    """
    return _WHITESPACE.sub(" ", text).strip()


def _extract_number(title: str) -> str:
    """Extract the leading statutory number from a title string.

    Returns the raw number token when present, otherwise returns the full
    title trimmed to 20 characters as a fallback identifier.

    Args:
        title: The section/part/chapter title text.

    Returns:
        str: Statutory number or a truncated title fallback.
    """
    m = _SECTION_NUM_RE.match(title.strip())
    return m.group(1) if m else title.strip()[:20]


def _kind_from_text(label: str) -> Literal["part", "chapter", "section", "subsection", "clause"]:
    """Infer the provision kind from a heading label string.

    Args:
        label: Lower-cased heading or class-name token.

    Returns:
        Literal: The most specific kind that matches.
    """
    label_lower = label.lower()
    if "part" in label_lower:
        return "part"
    if "chapter" in label_lower or "chap" in label_lower:
        return "chapter"
    if "sub" in label_lower:
        return "subsection"
    if "clause" in label_lower:
        return "clause"
    return "section"


def _node_text(node: Node) -> str:
    """Extract clean provision text from a DOM node.

    Args:
        node: selectolax ``Node`` to extract text from.

    Returns:
        str: Clean provision text.
    """
    raw = node.text(deep=True, separator=" ")
    return clean_provision_text(raw) if raw else ""


class _Parser:
    """Stateful DOM walker that builds a ProvisionNode tree.

    Handles the bdlaws HTML structure, which places section and chapter
    containers in ``<div>`` elements distinguished by CSS class names or
    heading tags (``<h2>``–``<h5>``).
    """

    def __init__(self, source_url: str) -> None:
        """Initialise the parser.

        Args:
            source_url: The canonical URL of the page being parsed, carried
                into every node.
        """
        self._source_url = source_url
        self.warnings: list[ParseWarning] = []

    def _warn(self, message: str, context: str = "") -> None:
        """Record a non-fatal warning.

        Args:
            message: Description of the unexpected pattern.
            context: Optional HTML snippet for debugging.
        """
        logger.warning("parse warning: %s", message, extra={"context": context[:200]})
        self.warnings.append(ParseWarning(message=message, context=context[:200]))

    def parse(self, html: str) -> ProvisionNode:
        """Parse a full bdlaws page HTML string into a ProvisionNode tree.

        Tries several known bdlaws HTML structural patterns. Falls back to
        a flat section list from heading elements when no recognised container
        is found. Always returns a valid ``"act"`` root node — never raises.

        Args:
            html: Full page HTML from bdlaws.

        Returns:
            ProvisionNode: Root act node containing all extracted provisions.
        """
        tree = HTMLParser(html)

        # --- Act title ---
        act_title = self._extract_act_title(tree)

        # --- Content container: try known selectors, then <body> fallback ---
        content = (
            tree.css_first(".lawCon")
            or tree.css_first("#sub_section_content")
            or tree.css_first(".act_content")
            or tree.css_first("#law_content")
            or tree.css_first(".sectionBody")
            or tree.body
        )
        if content is None:
            self._warn("no recognisable content container found; using raw page text")
            raw_text = extract_text(html)
            return ProvisionNode(
                kind="act",
                number="0",
                title=act_title,
                text=raw_text,
                children=(),
                effective_from=None,
                effective_to=None,
                source_url=self._source_url,
            )

        children = self._extract_children(content)

        return ProvisionNode(
            kind="act",
            number="0",
            title=act_title,
            text="",
            children=tuple(children),
            effective_from=None,
            effective_to=None,
            source_url=self._source_url,
        )

    def _extract_act_title(self, tree: HTMLParser) -> str | None:
        """Extract the Act title from common bdlaws title elements.

        Args:
            tree: The parsed HTML tree.

        Returns:
            str | None: The act title, or ``None`` if not found.
        """
        for selector in (".act_title", ".act-title", "#act_title", "h1", ".lawTitle"):
            node = tree.css_first(selector)
            if node:
                title = _norm(node.text(deep=True))
                if title:
                    return title
        return None

    def _extract_children(self, container: Node) -> list[ProvisionNode]:
        """Walk a container node and extract all provisions.

        Handles both div-based and table-based bdlaws layouts. Section and
        chapter boundaries are identified by CSS classes and heading elements.

        Args:
            container: The content container DOM node.

        Returns:
            list[ProvisionNode]: Top-level provisions found in the container.
        """
        children: list[ProvisionNode] = []

        # --- Attempt 1: explicit section/chapter divs ---
        structural = container.css(
            ".section, .chapter, .part, [class*='sec_'], [class*='section'], [class*='chapter']"
        )
        if structural:
            for node in structural:
                # Skip nodes that are children of another structural node already processed.
                provision = self._parse_structural_node(node)
                if provision is not None:
                    children.append(provision)
            return children

        # --- Attempt 2: heading-delimited sections ---
        headings = container.css("h2, h3, h4, h5")
        if headings:
            children = self._parse_heading_sections(container, headings)
            return children

        # --- Attempt 3: table-based layout (bdlaws classic style) ---
        tables = container.css("table.section, table.chtitle, table.chapter, table[class]")
        if tables:
            children = self._parse_table_sections(tables)
            return children

        # --- Fallback: flat text extraction ---
        text = _node_text(container)
        if text:
            children.append(
                ProvisionNode(
                    kind="section",
                    number="1",
                    title=None,
                    text=text,
                    children=(),
                    effective_from=None,
                    effective_to=None,
                    source_url=self._source_url,
                )
            )
        else:
            self._warn(
                "content container yielded no provisions",
                container.html or "",
            )
        return children

    def _parse_structural_node(self, node: Node) -> ProvisionNode | None:
        """Parse a single structural div (section, chapter, part) node.

        Args:
            node: The structural DOM node.

        Returns:
            ProvisionNode | None: Parsed node, or ``None`` if unrecognisable.
        """
        css_class = " ".join((node.attributes.get("class") or "").split()).lower()
        kind = _kind_from_text(css_class)

        # Title: look for a heading within the node.
        title_node = (
            node.css_first(".sec_head")
            or node.css_first(".sec-title")
            or node.css_first(".section_title")
            or node.css_first(".chapter_title")
            or node.css_first("h2")
            or node.css_first("h3")
            or node.css_first("h4")
        )
        title_text: str | None = None
        if title_node:
            title_text = _norm(title_node.text(deep=True)) or None

        number = _extract_number(title_text or "") if title_text else "?"

        # Body text: prefer explicit body containers, fall back to full node.
        body_node = (
            node.css_first(".sec_content")
            or node.css_first(".sec-body")
            or node.css_first(".section_body")
            or node.css_first(".secBody")
        )
        if body_node:
            text = _node_text(body_node)
        else:
            # Remove the title text from the full node text to get just the body.
            full_text = _node_text(node)
            if title_text and full_text.startswith(title_text):
                text = clean_provision_text(full_text[len(title_text) :])
            else:
                text = full_text

        # Nested children (subsections, clauses).
        nested = node.css(".sub_section, .subsection, .clause, [class*='sub_']")
        nested_children: list[ProvisionNode] = []
        for sub in nested:
            sub_node = self._parse_sub_node(sub)
            if sub_node is not None:
                nested_children.append(sub_node)

        return ProvisionNode(
            kind=kind,
            number=number,
            title=title_text,
            text="" if nested_children else text,
            children=tuple(nested_children),
            effective_from=None,
            effective_to=None,
            source_url=self._source_url,
        )

    def _parse_sub_node(self, node: Node) -> ProvisionNode | None:
        """Parse a subsection or clause node.

        Args:
            node: The subsection/clause DOM node.

        Returns:
            ProvisionNode | None: Parsed subprovision, or ``None``.
        """
        css_class = " ".join((node.attributes.get("class") or "").split()).lower()
        kind: Literal["subsection", "clause"] = "clause" if "clause" in css_class else "subsection"

        num_node = node.css_first(".sub_num, .clause_num, [class*='num']")
        number = _norm(num_node.text(deep=True)).strip("()") if num_node else "?"

        text_node = node.css_first(".sub_text, .clause_text, [class*='text']")
        text = _node_text(text_node) if text_node else _node_text(node)

        if not text:
            return None

        return ProvisionNode(
            kind=kind,
            number=number,
            title=None,
            text=text,
            children=(),
            effective_from=None,
            effective_to=None,
            source_url=self._source_url,
        )

    def _parse_heading_sections(self, container: Node, headings: list[Node]) -> list[ProvisionNode]:
        """Build provisions by treating heading elements as section boundaries.

        Args:
            container: The parent container node.
            headings: Heading nodes found inside the container.

        Returns:
            list[ProvisionNode]: Provisions delimited by the heading elements.
        """
        provisions: list[ProvisionNode] = []

        # Collect text following each heading until the next heading.
        # This is a heuristic: we walk the serialised text of the container.
        full_html = container.html or ""
        temp = HTMLParser(full_html)
        all_nodes = list(temp.css("h2, h3, h4, h5, p, div, td"))

        pending_title: str | None = None
        pending_kind: Literal["part", "chapter", "section", "subsection", "clause"] = "section"
        pending_number = "?"
        buffer: list[str] = []
        heading_tags = {"h2", "h3", "h4", "h5"}

        def flush() -> None:
            nonlocal pending_title, pending_number, buffer
            text = clean_provision_text(" ".join(buffer))
            if text or pending_title:
                provisions.append(
                    ProvisionNode(
                        kind=pending_kind,
                        number=pending_number,
                        title=pending_title,
                        text=text,
                        children=(),
                        effective_from=None,
                        effective_to=None,
                        source_url=self._source_url,
                    )
                )
            buffer = []
            pending_title = None

        for node in all_nodes:
            if node.tag in heading_tags:
                flush()
                pending_title = _norm(node.text(deep=True)) or None
                pending_kind = _kind_from_text(pending_title or "")
                pending_number = _extract_number(pending_title or "")
            else:
                text = _norm(node.text(deep=True))
                if text:
                    buffer.append(text)

        flush()
        return provisions

    def _parse_table_sections(self, tables: list[Node]) -> list[ProvisionNode]:
        """Extract provisions from table-based bdlaws layouts.

        Args:
            tables: Structural table nodes found in the content.

        Returns:
            list[ProvisionNode]: Provisions extracted from the tables.
        """
        provisions: list[ProvisionNode] = []
        for table in tables:
            css_class = (table.attributes.get("class") or "").lower()
            kind = _kind_from_text(css_class)

            # Title: first row of the table typically holds the heading.
            title_node = table.css_first(".sec_head, th, .header td")
            title_text = _norm(title_node.text(deep=True)) if title_node else None
            number = _extract_number(title_text or "") if title_text else "?"

            # Body: all remaining text.
            full = _node_text(table)
            body = (
                clean_provision_text(full[len(title_text) :])
                if title_text and full.startswith(title_text)
                else full
            )

            if body or title_text:
                provisions.append(
                    ProvisionNode(
                        kind=kind,
                        number=number,
                        title=title_text,
                        text=body,
                        children=(),
                        effective_from=None,
                        effective_to=None,
                        source_url=self._source_url,
                    )
                )
        return provisions


def parse_act_page(html: str, source_url: str) -> ParseResult:
    """Parse a bdlaws Act page HTML into a ProvisionNode tree.

    The parser is defensive: it never raises on missing optional elements and
    records unrecognised patterns as :class:`ParseWarning` objects. Always
    returns a valid ``"act"`` root node.

    Args:
        html: Full page HTML from bdlaws.
        source_url: Canonical URL of the page, embedded in every node.

    Returns:
        ParseResult: The root act node and any non-fatal warnings.
    """
    parser = _Parser(source_url)
    try:
        root = parser.parse(html)
    except Exception as exc:  # noqa: BLE001 — defensive; never let parser kill ingestion
        logger.exception("unexpected parser error; falling back to empty act node")
        parser.warnings.append(ParseWarning(message=f"unexpected error: {exc}"))
        root = ProvisionNode(
            kind="act",
            number="0",
            title=None,
            text="",
            children=(),
            effective_from=None,
            effective_to=None,
            source_url=source_url,
        )
    return ParseResult(root=root, warnings=parser.warnings)
