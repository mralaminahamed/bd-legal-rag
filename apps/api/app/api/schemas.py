"""Pydantic v2 request and response schemas for the public and admin API.

All endpoint I/O is typed through these models; SQLAlchemy ORM objects never
leave the service layer (architecture §2.6, NFR-MN-*).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Public query request.

    Attributes:
        question: The user's natural-language question (BN or EN).
        act_slug: Optional slug scoping retrieval to a single Act.
        language: Explicitly request a response language; ``None`` auto-detects.
        as_of_date: View the corpus as it stood on this date (FR-QR-6).
    """

    question: str = Field(min_length=1, max_length=2000)
    act_slug: str | None = None
    language: str | None = Field(default=None, pattern=r"^(bn|en)$")
    as_of_date: date | None = None


class FeedbackRequest(BaseModel):
    """User feedback on a prior query.

    Attributes:
        query_id: The UUID of the query this feedback relates to.
        rating: One of the four structured ratings.
        comment: Optional free-text comment.
    """

    query_id: str
    rating: str = Field(pattern=r"^(helpful|not_helpful|wrong_citation|out_of_scope)$")
    comment: str | None = Field(default=None, max_length=2000)


class IngestRequest(BaseModel):
    """Admin ingestion trigger.

    Attributes:
        force: Re-ingest even when the content hash is unchanged.
    """

    force: bool = False
