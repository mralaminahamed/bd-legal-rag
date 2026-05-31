"""Versioned bilingual disclaimer (NFR-LS-1, docs/01-SRS.md §7).

The disclaimer is APPLICATION output — it is appended by ``inject()`` after
generation and is never included in a prompt.  Every user-facing response
path must call ``inject()``.  Cache-hits re-assert the active disclaimer
version and refresh the stored text if the version has changed.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Disclaimer:
    """A versioned bilingual disclaimer.

    Attributes:
        version: Version string (e.g. ``v1``).
        en: English disclaimer text.
        bn: Bengali disclaimer text.
    """

    version: str
    en: str
    bn: str


_REGISTRY: dict[str, Disclaimer] = {
    "v1": Disclaimer(
        version="v1",
        en=(
            "**Disclaimer:** This response is for informational and research purposes only "
            "and does not constitute legal advice. The information is based on publicly "
            "available statutory text from bdlaws.minlaw.gov.bd. Laws may have been amended "
            "after the date of this text. For legal advice specific to your situation, "
            "please consult a qualified legal professional."
        ),
        bn=(
            "**দায়বর্জন বিবৃতি:** এই প্রতিক্রিয়াটি কেবল তথ্যগত ও গবেষণা উদ্দেশ্যে প্রদান করা হয়েছে "
            "এবং এটি কোনো আইনি পরামর্শ নয়। তথ্যটি bdlaws.minlaw.gov.bd থেকে প্রকাশিত আইনি টেক্সটের "
            "উপর ভিত্তি করে তৈরি। এই টেক্সটের তারিখের পরে আইন পরিবর্তিত হয়ে থাকতে পারে। "
            "আপনার নির্দিষ্ট পরিস্থিতির জন্য আইনি পরামর্শের জন্য একজন যোগ্য আইনজীবীর সাথে "
            "পরামর্শ করুন।"
        ),
    ),
}


def resolve(version: str) -> Disclaimer:
    """Return the ``Disclaimer`` for *version*.

    Args:
        version: Version string (e.g. ``v1``).

    Returns:
        Disclaimer: The corresponding disclaimer.

    Raises:
        KeyError: If *version* is not registered.
    """
    if version not in _REGISTRY:
        raise KeyError(f"unknown disclaimer version: {version!r}")
    return _REGISTRY[version]


def inject(
    response_text: str,
    *,
    version: str,
    language: str,
) -> str:
    """Append the active disclaimer to *response_text*.

    Must be called on every user-facing response path — normal, decline,
    fail-open, cache-hit, and error responses (NFR-LS-1).

    Args:
        response_text: Generated or constructed response text.
        version: Active disclaimer version from config.
        language: Response language (``bn`` or ``en``).

    Returns:
        str: ``response_text`` followed by a blank line and the disclaimer.
    """
    disclaimer = resolve(version)
    text = disclaimer.bn if language == "bn" else disclaimer.en
    return f"{response_text}\n\n{text}"
