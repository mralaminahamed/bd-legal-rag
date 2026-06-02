"""Versioned prompt registry (architecture §2.5).

Resolves a ``PromptTemplate`` by family and version string.  Active versions
are set in ``app/config.py`` and read at call time — never hardcoded.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from typing import Any


def _load_registry() -> dict[str, Any]:
    from app.prompts.families.legal_answer import v1 as legal_answer_v1
    from app.prompts.families.legal_answer import v2 as legal_answer_v2

    return {
        "legal_answer:v1": legal_answer_v1,
        "legal_answer:v2": legal_answer_v2,
    }


_REGISTRY: dict[str, Any] = _load_registry()


def resolve(family: str, version: str) -> Any:
    """Return the prompt template module for *family* and *version*.

    Args:
        family: Prompt family name (e.g. ``legal_answer``).
        version: Version string (e.g. ``v2``).

    Returns:
        A module with a ``render()`` function and a ``VERSION`` attribute.

    Raises:
        KeyError: If the family/version combination is not registered.
    """
    key = f"{family}:{version}"
    if key not in _REGISTRY:
        raise KeyError(f"unknown prompt: {key!r}")
    return _REGISTRY[key]
