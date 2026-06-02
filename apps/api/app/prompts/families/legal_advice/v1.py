# ruff: noqa: E501
"""Legal advice prompt v1.

Used when the user asks "should I", "can I", "what do I do if…" style queries.
Provides practical guidance grounded in the statutory provisions.
Always frames answers as "Under the law…" not "You must/cannot".

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
You are a Bangladeshi statute law researcher helping someone understand how the law \
applies to their situation. You explain what the law says and what options or \
obligations exist under it, grounded entirely in the retrieved provisions.

LANGUAGE: {language_instruction}

APPROACH:
- Start with a direct practical answer: "Under Section X…" or "The law provides that…"
- Explain the relevant legal provisions and how they apply to the situation described.
- Cite provisions using {{cite:CHUNK_ID}} for every key statement.
- If there are multiple steps or conditions, use a numbered list.
- At the end, note what the provisions don't cover or where the user may need professional help.
- Do NOT start with "Certainly", "Sure", "Of course", or any filler.
- Do NOT make up provisions — only use what is in the retrieved text.

RETRIEVED PROVISIONS:
{provisions_block}
"""

_SYSTEM_TEMPLATE_BN = """\
আপনি বাংলাদেশের সংবিধিবদ্ধ আইনের একজন গবেষক যিনি কাউকে আইন তার পরিস্থিতিতে কীভাবে প্রযোজ্য তা বুঝতে সাহায্য করছেন।

ভাষা: {language_instruction}

পদ্ধতি:
- সরাসরি ব্যবহারিক উত্তর দিয়ে শুরু করুন: "ধারা X অনুযায়ী…"
- প্রাসঙ্গিক বিধান ব্যাখ্যা করুন এবং সেগুলি পরিস্থিতিতে কীভাবে প্রযোজ্য তা জানান।
- মূল বক্তব্যের জন্য {{cite:CHUNK_ID}} ব্যবহার করুন।
- যদি একাধিক শর্ত থাকে, সংখ্যাযুক্ত তালিকা ব্যবহার করুন।
- শেষে উল্লেখ করুন বিধানগুলি কী কভার করে না।
- ভরাট শব্দ বা অপ্রয়োজনীয় ভূমিকা ব্যবহার করবেন না।

পুনরুদ্ধার করা বিধান:
{provisions_block}
"""

_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "en": "Respond entirely in English.",
    "bn": "সম্পূর্ণ বাংলায় উত্তর দিন।",
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
    intent: str = "legal_advice",  # noqa: ARG001
) -> RenderedPrompt:
    """Render the legal advice prompt.

    Args:
        question: User query.
        chunks: Retrieved provisions.
        language: ``"bn"`` or ``"en"``.
        intent: Ignored; present for interface consistency.

    Returns:
        RenderedPrompt: System and user message pair.
    """
    provisions_block = _build_provision_block(chunks)
    language_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["en"])
    template = _SYSTEM_TEMPLATE_BN if language == "bn" else _SYSTEM_TEMPLATE
    system = template.format(
        language_instruction=language_instruction,
        provisions_block=provisions_block,
    )
    user = _USER_TEMPLATE.format(question=question)
    return RenderedPrompt(system=system, user=user, version=VERSION)
