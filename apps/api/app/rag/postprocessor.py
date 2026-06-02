"""Response post-processor — strips filler openers from LLM output.

Targets the most common slop patterns produced by small instruction-tuned
models regardless of prompt instructions.  Applied after citation resolution,
before disclaimer injection.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import re

# English filler openers — case-insensitive prefix patterns
_EN_FILLER = re.compile(
    r"^(?:"
    r"\*\*answer:\*\*\s*|"
    r"answer:\s*|"
    r"certainly[!,.]?\s*|"
    r"sure[!,.]?\s*|"
    r"of\s+course[!,.]?\s*|"
    r"great\s+question[!,.]?\s*|"
    r"good\s+question[!,.]?\s*|"
    r"absolutely[!,.]?\s*|"
    r"thank\s+you\s+for\s+(?:your\s+)?question[!,.]?\s*|"
    r"based\s+on\s+the\s+(?:provided|retrieved)\s+provisions?,?\s*|"
    r"according\s+to\s+the\s+(?:provided|retrieved)\s+provisions?,?\s*|"
    r"as\s+per\s+the\s+(?:provided|retrieved|above)?\s*(?:law|provisions?|act)?,?\s*|"
    r"the\s+retrieved\s+provisions?\s+(?:state|indicate|show|suggest)s?\s+that\s*|"
    r"based\s+on\s+(?:my\s+)?(?:analysis\s+of\s+)?the\s+(?:above|provided|given)\s*[^,\n]*,?\s*"
    r")",
    re.IGNORECASE,
)

# Bengali filler openers
_BN_FILLER = re.compile(
    r"^(?:"
    r"\*\*উত্তর:\*\*\s*|"
    r"উত্তর:\s*|"
    r"অবশ্যই[!,।]?\s*|"
    r"নিশ্চয়ই[!,।]?\s*|"
    r"অবশ্যই[!,।]?\s*|"
    r"প্রদত্ত বিধান অনুযায়ী,?\s*|"
    r"উপরোক্ত বিধান অনুযায়ী,?\s*|"
    r"পুনরুদ্ধার করা বিধান অনুযায়ী,?\s*|"
    r"প্রদত্ত তথ্য অনুযায়ী,?\s*|"
    r"আপনার প্রশ্নের উত্তরে,?\s*"
    r")",
)


def strip_filler(text: str) -> str:
    """Remove known LLM filler openers from the start of *text*.

    Applies English patterns first, then Bengali. Strips iteratively so
    stacked openers ("Certainly! Based on the provisions...") are all removed.

    Args:
        text: Raw LLM output text.

    Returns:
        str: Text with filler openers removed, leading whitespace stripped.
    """
    changed = True
    while changed:
        prev = text
        text = _EN_FILLER.sub("", text).lstrip()
        text = _BN_FILLER.sub("", text).lstrip()
        changed = text != prev
    return text
