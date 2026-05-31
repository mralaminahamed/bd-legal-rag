"""Ingestion result model.

A Pydantic model describing the outcome of ingesting one ``(act, language)``
pair, returned by the ingestion task and surfaced via the admin API.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

RunStatus = Literal["succeeded", "failed"]


class IngestSummary(BaseModel):
    """Outcome of ingesting one ``(act, language)`` pair.

    Attributes:
        act_id: The Act that was ingested.
        language: Language variant (``bn`` or ``en``).
        status: Terminal run status.
        provisions_new: Count of newly inserted provisions/revisions.
        provisions_updated: Count of revisions whose text changed.
        provisions_unchanged: Count of revisions skipped by content hash (FR-IN-4).
        chunks_created: Count of chunks produced (non-zero after Phase 3 wires embedding).
        error: Failure detail when ``status`` is ``"failed"``.
    """

    act_id: uuid.UUID
    language: Literal["bn", "en"]
    status: RunStatus
    provisions_new: int = 0
    provisions_updated: int = 0
    provisions_unchanged: int = 0
    chunks_created: int = 0
    error: str | None = None
