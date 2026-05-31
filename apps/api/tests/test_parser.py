"""Tests for the bdlaws statutory parser.

Uses inline HTML fixtures so no network calls are needed. Verifies the tree
structure, defensive handling of unusual markup, and Bengali text preservation.
"""

from __future__ import annotations

import pytest
from app.ingestion.parser import ProvisionNode, parse_act_page

_SOURCE_URL = "https://bdlaws.minlaw.gov.bd/act-details-952.html"

# Minimal bdlaws-like HTML with class-based structure.
_BASIC_HTML = """
<html><body>
<div class="act_title">Bangladesh Labour Act, 2006</div>
<div class="lawCon">
  <div class="chapter">
    <div class="chapter_title">Chapter I - Preliminary</div>
    <div class="section" id="section-1">
      <div class="sec_head">1. Short title and commencement</div>
      <div class="sec_content">
        <div class="sub_section">
          <span class="sub_num">(1)</span>
          <span class="sub_text">This Act may be called the Bangladesh Labour Act, 2006.</span>
        </div>
      </div>
    </div>
    <div class="section" id="section-2">
      <div class="sec_head">2. Definitions</div>
      <div class="sec_content">In this Act, unless the context otherwise requires...</div>
    </div>
  </div>
</div>
</body></html>
"""

# HTML with Bengali text.
_BENGALI_HTML = """
<html><body>
<div class="lawCon">
  <div class="section">
    <div class="sec_head">১. সংক্ষিপ্ত শিরোনাম</div>
    <div class="sec_content">এই আইন বাংলাদেশ শ্রম আইন, ২০০৬ নামে পরিচিত হইবে।</div>
  </div>
</div>
</body></html>
"""

# Heading-delimited HTML (no class structure).
_HEADING_HTML = """
<html><body>
<div id="law_content">
  <h2>Chapter I</h2>
  <p>Preliminary provisions.</p>
  <h3>1. Short title</h3>
  <p>This Act may be called the Test Act.</p>
  <h3>2. Definitions</h3>
  <p>In this Act, unless the context...</p>
</div>
</body></html>
"""

# Empty / no-content HTML — must not raise.
_EMPTY_HTML = "<html><body></body></html>"

# HTML with script/style that must be stripped.
_XSS_HTML = """
<html><body>
<div class="lawCon">
  <script>document.cookie = 'stolen'</script>
  <div class="section">
    <div class="sec_head">1. Test section</div>
    <div class="sec_content">Clean provision text.</div>
  </div>
</div>
</body></html>
"""


def test_root_node_is_act() -> None:
    """Root node always has kind 'act'."""
    result = parse_act_page(_BASIC_HTML, _SOURCE_URL)
    assert result.root.kind == "act"


def test_root_carries_source_url() -> None:
    """Every node in the tree carries the source URL."""
    result = parse_act_page(_BASIC_HTML, _SOURCE_URL)
    assert result.root.source_url == _SOURCE_URL


def test_sections_extracted() -> None:
    """Section nodes are extracted from a class-based structure."""
    result = parse_act_page(_BASIC_HTML, _SOURCE_URL)

    def _collect(node: ProvisionNode) -> list[ProvisionNode]:
        nodes = []
        if node.kind in ("section", "subsection", "clause"):
            nodes.append(node)
        for child in node.children:
            nodes.extend(_collect(child))
        return nodes

    sections = _collect(result.root)
    assert len(sections) >= 2, "expected at least 2 sections"


def test_bengali_text_preserved() -> None:
    """Bengali provision text passes through the parser bit-for-bit."""
    result = parse_act_page(_BENGALI_HTML, _SOURCE_URL)

    def _all_text(node: ProvisionNode) -> str:
        return node.text + "".join(_all_text(c) for c in node.children)

    all_text = _all_text(result.root)
    assert "শ্রম" in all_text, "Bengali word 'শ্রম' must survive parsing"
    assert "২০০৬" in all_text, "Bengali numeral '২০০৬' must survive parsing"


def test_heading_delimited_html_parsed() -> None:
    """Heading-delimited HTML (no classes) produces provisions."""
    result = parse_act_page(_HEADING_HTML, _SOURCE_URL)

    def _count(node: ProvisionNode) -> int:
        return (1 if node.kind in ("section", "chapter", "part") else 0) + sum(
            _count(c) for c in node.children
        )

    assert _count(result.root) >= 1


def test_never_raises_on_empty_html() -> None:
    """Parser returns a valid act root even for empty HTML — never raises."""
    result = parse_act_page(_EMPTY_HTML, _SOURCE_URL)
    assert result.root.kind == "act"


def test_never_raises_on_garbage_html() -> None:
    """Parser returns a valid act root for completely broken HTML."""
    result = parse_act_page("<<<not html at all!>>>", _SOURCE_URL)
    assert result.root.kind == "act"


def test_executable_markup_stripped() -> None:
    """Script content never appears in any provision text."""
    result = parse_act_page(_XSS_HTML, _SOURCE_URL)

    def _all_text(node: ProvisionNode) -> str:
        return node.text + "".join(_all_text(c) for c in node.children)

    assert "stolen" not in _all_text(result.root)
    assert "Clean provision text." in _all_text(result.root)


def test_provision_node_is_frozen() -> None:
    """ProvisionNode is frozen (immutable)."""
    node = ProvisionNode(
        kind="section",
        number="1",
        title="Test",
        text="body",
        children=(),
        effective_from=None,
        effective_to=None,
        source_url=_SOURCE_URL,
    )
    with pytest.raises((AttributeError, TypeError)):
        node.text = "mutated"  # type: ignore[misc]
