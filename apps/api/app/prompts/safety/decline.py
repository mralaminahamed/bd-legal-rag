"""Versioned bilingual decline response text (NFR-LS-3).

The decline text is canonical and version-controlled.  It is returned by the
decline gate and passed through ``disclaimer.inject()`` before reaching the
user.  The LLM is never called on the decline path.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeclineText:
    """A versioned bilingual decline message.

    Attributes:
        version: Version string (e.g. ``v1``).
        en: English decline message.
        bn: Bengali decline message.
    """

    version: str
    en: str
    bn: str


_REGISTRY: dict[str, DeclineText] = {
    "v1": DeclineText(
        version="v1",
        en=(
            "I'm unable to provide advice on your specific situation. This service is a "
            "statutory research tool for looking up provisions of Bangladeshi law — it does "
            "not give personalised legal advice. For guidance on what you should do, please "
            "consult a qualified legal professional."
        ),
        bn=(
            "আমি আপনার নির্দিষ্ট পরিস্থিতির বিষয়ে পরামর্শ দিতে অক্ষম। এই সেবাটি বাংলাদেশের আইনের "
            "বিধান অনুসন্ধানের জন্য একটি বিধিবদ্ধ গবেষণা সরঞ্জাম — এটি ব্যক্তিগত আইনি পরামর্শ "
            "প্রদান করে না। আপনার কী করা উচিত সে বিষয়ে নির্দেশনার জন্য অনুগ্রহ করে একজন যোগ্য "
            "আইনজীবীর সাথে পরামর্শ করুন।"
        ),
    ),
}


def resolve(version: str) -> DeclineText:
    """Return the ``DeclineText`` for *version*.

    Args:
        version: Version string (e.g. ``v1``).

    Returns:
        DeclineText: The corresponding decline text.

    Raises:
        KeyError: If *version* is not registered.
    """
    if version not in _REGISTRY:
        raise KeyError(f"unknown decline version: {version!r}")
    return _REGISTRY[version]
