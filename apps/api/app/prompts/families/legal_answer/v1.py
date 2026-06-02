"""Legal-answer prompt v1 (architecture §2.5, NFR-SC-3).

The question is fenced in a ``<question>`` block to prevent prompt injection.
Each retrieved provision is fenced in its own ``<provision>`` block with a
``{{cite:chunk_id}}`` placeholder.  The disclaimer is NOT in this prompt.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk

VERSION = "v1"
version = VERSION  # module-level alias for registry consumers

_SYSTEM_TEMPLATE = """\
You are a legal research assistant for Bangladeshi statute law (bdlaws.minlaw.gov.bd).
Your role is to help users understand provisions of the law — NOT to give legal advice.

LANGUAGE: {language_instruction}

STRICT RULES:
1. Every normative statement (what the law requires, permits, or prohibits) MUST cite the exact
   provision using the placeholder {{cite:CHUNK_ID}} where CHUNK_ID is the identifier shown
   in the provision block.
2. You MUST NEVER assert a legal conclusion in your own voice.
   FORBIDDEN phrases: "you must", "you cannot", "it is illegal", "you are required to",
   and their Bengali equivalents.
3. Attribute all statements to the cited provision. If the provisions are ambiguous, say so.
4. Do not summarise or paraphrase without citing. If the answer is not in the provisions, say so.

RETRIEVED PROVISIONS:
{provisions_block}
"""

_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "en": (
        "You MUST respond entirely in English regardless of the language"
        " of the retrieved provisions."
    ),
    "bn": (
        "আপনাকে অবশ্যই সম্পূর্ণ বাংলায় উত্তর দিতে হবে,"
        " পুনরুদ্ধার করা বিধানের ভাষা নির্বিশেষে।"
    ),
}

_USER_TEMPLATE = """\
<question>
{question}
</question>
"""


@dataclass(frozen=True)
class RenderedPrompt:
    """A rendered, ready-to-send prompt pair.

    Attributes:
        system: System prompt text (provision context, rules).
        user: User message text (fenced question only).
        version: Template version string.
    """

    system: str
    user: str
    version: str


def _build_provision_block(chunks: list[RetrievedChunk]) -> str:
    lines: list[str] = []
    for chunk in chunks:
        lines.append(
            f'<provision chunk_id="{chunk.chunk_id}" path="{chunk.hierarchy_path}">\n'
            f"{chunk.content}\n"
            f"</provision>\n"
            f"To cite this provision use: {{{{cite:{chunk.chunk_id}}}}}"
        )
    return "\n\n".join(lines)


def render(
    question: str,
    chunks: list[RetrievedChunk],
    language: str,
) -> RenderedPrompt:
    """Render the v1 legal-answer prompt.

    Args:
        question: The user's question (placed in a fenced block in ``user``).
        chunks: Retrieved provisions to supply as context.
        language: Detected query language (``bn`` or ``en``); injected as an
            explicit language instruction so the model cannot fall back to the
            language of the retrieved provisions (which may differ).

    Returns:
        RenderedPrompt: System and user message pair.
    """
    provisions_block = _build_provision_block(chunks)
    language_instruction = _LANGUAGE_INSTRUCTIONS.get(
        language,
        _LANGUAGE_INSTRUCTIONS["en"],
    )
    system = _SYSTEM_TEMPLATE.format(
        language_instruction=language_instruction,
        provisions_block=provisions_block,
    )
    user = _USER_TEMPLATE.format(question=question)
    return RenderedPrompt(system=system, user=user, version=VERSION)
