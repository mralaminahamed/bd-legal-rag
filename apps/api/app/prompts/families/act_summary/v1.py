# ruff: noqa: E501
"""Act summary / explain prompt v1.

Used for: summarize, explain, overview, "what does X cover?" queries.
Does not enforce citation-per-sentence — synthesises from all retrieved chunks.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk

VERSION = "v1"
version = VERSION

_SYSTEM_TEMPLATE = """\
You are a Bangladeshi statute law researcher. Using the retrieved provisions below, \
write a clear {mode} of this Act.

LANGUAGE: {language_instruction}

INSTRUCTIONS:
- Write in flowing prose, not bullet lists.
- Cite key provisions using {cite:CHUNK_ID} where relevant, but do not over-cite.
- Structure: what the Act is about → who it applies to → key provisions/rights/obligations → penalties if any.
- Be informative and clear. Avoid legalese unless quoting directly.
- Do not start with "Certainly", "Sure", "Based on", or any filler phrase.
- Keep to 3-5 paragraphs.

RETRIEVED PROVISIONS:
{provisions_block}
"""

_SYSTEM_TEMPLATE_BN = """\
আপনি বাংলাদেশের সংবিধিবদ্ধ আইনের একজন গবেষক। নিচে দেওয়া বিধানগুলি ব্যবহার করে এই আইনের একটি স্পষ্ট {mode} লিখুন।

ভাষা: {language_instruction}

নির্দেশনা:
- গদ্যে লিখুন, বুলেট তালিকায় নয়।
- প্রাসঙ্গিক ক্ষেত্রে {{cite:CHUNK_ID}} ব্যবহার করে বিধান উদ্ধৃত করুন।
- গঠন: আইনটি কী বিষয়ে → কার জন্য প্রযোজ্য → মূল বিধান → শাস্তির বিধান (যদি থাকে)।
- সরাসরি শুরু করুন — কোনো ভূমিকা বা ভরাট শব্দ ব্যবহার করবেন না।

পুনরুদ্ধার করা বিধান:
{provisions_block}
"""

_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "en": "Respond entirely in English.",
    "bn": "সম্পূর্ণ বাংলায় উত্তর দিন।",
}

_MODES: dict[str, dict[str, str]] = {
    "act_summary": {"en": "summary", "bn": "সারসংক্ষেপ"},
    "act_explain": {"en": "explanation", "bn": "ব্যাখ্যা"},
}

_USER_TEMPLATE = "<question>\n{question}\n</question>"


@dataclass(frozen=True)
class RenderedPrompt:
    """Rendered prompt pair.

    Attributes:
        system: System prompt text.
        user: User message.
        version: Template version.
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
            f"To cite this provision use: {{cite:{chunk.chunk_id}}}"
        )
    return "\n\n".join(lines)


def render(
    question: str,
    chunks: list[RetrievedChunk],
    language: str,
    intent: str = "act_summary",
) -> RenderedPrompt:
    """Render the act summary/explain prompt.

    Args:
        question: User query.
        chunks: Retrieved provisions.
        language: ``"bn"`` or ``"en"``.
        intent: ``"act_summary"`` or ``"act_explain"``.

    Returns:
        RenderedPrompt: System and user message pair.
    """
    provisions_block = _build_provision_block(chunks)
    language_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["en"])
    mode = _MODES.get(intent, _MODES["act_summary"])[language if language == "bn" else "en"]
    template = _SYSTEM_TEMPLATE_BN if language == "bn" else _SYSTEM_TEMPLATE
    system = template.format(
        mode=mode,
        language_instruction=language_instruction,
        provisions_block=provisions_block,
    )
    user = _USER_TEMPLATE.format(question=question)
    return RenderedPrompt(system=system, user=user, version=VERSION)
