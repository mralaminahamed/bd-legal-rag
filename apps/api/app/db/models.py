"""SQLAlchemy 2.0 declarative models.

Mirrors the schema in ``docs/02-Architecture.md`` §3.2 exactly: acts,
provisions, provision_revisions, chunks, ingestion_runs, queries, and feedback,
including the ``vector(1024)`` embedding column (ADR-002), the generated
``tsvector`` lexical column with the ``simple`` configuration (ADR-007), and
every constraint, unique, and index.

Bengali has no Postgres dictionary so the lexical column always uses the
``simple`` configuration. Switching to ``english`` would break Bengali recall
and must never happen (ADR-007).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Embedding width is fixed at 2560 for embed-multilingual-v3.0 (ADR-002).
# The HNSW operator class is vector_cosine_ops.
EMBED_DIMENSIONS = 2560
HNSW_OPS = "halfvec_cosine_ops"

# Allowed enumerations — kept identical to the DDL CHECK constraints.
PROVISION_KINDS = ("part", "chapter", "section", "subsection", "clause")
LANGUAGES = ("bn", "en")
TRANSLATION_STATUSES = ("authoritative", "reference_translation")
ACT_STATUSES = ("in_force", "partially_repealed", "repealed")
RUN_STATUSES = ("running", "succeeded", "failed")
CONFIDENCE_TIERS = ("HIGH", "MEDIUM", "LOW")
FEEDBACK_RATINGS = ("helpful", "not_helpful", "wrong_citation", "out_of_scope")


def _uuid_pk() -> Mapped[uuid.UUID]:
    """Return a UUID primary-key column defaulting to ``gen_random_uuid()``.

    Returns:
        Mapped[uuid.UUID]: The configured primary-key column.
    """
    return mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def _now() -> Mapped[datetime]:
    """Return a non-null ``timestamptz`` column defaulting to ``now()``.

    Returns:
        Mapped[datetime]: The timestamp column.
    """
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class Base(DeclarativeBase):
    """Declarative base carrying the shared metadata for all models."""


class Act(Base):
    """A registered Bangladeshi statute (FR-CM-1/2/3).

    Attributes:
        id: Surrogate primary key.
        slug: Unique operator-facing identifier (e.g. ``labour-act-2006``).
        short_name: Display name used in the UI.
        full_name_en: Official English title.
        full_name_bn: Official Bengali title.
        act_number: Roman-numeral act number (e.g. ``XLII``).
        act_year: Year of enactment.
        ministry: Responsible ministry, if known.
        status: Lifecycle status, one of :data:`ACT_STATUSES`.
        created_at: Row creation timestamp.
        provisions: Statutory tree rooted at this Act.
        ingestion_runs: Ingestion run history (per language).
    """

    __tablename__ = "acts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_force','partially_repealed','repealed')",
            name="acts_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    full_name_en: Mapped[str] = mapped_column(Text, nullable=False)
    full_name_bn: Mapped[str] = mapped_column(Text, nullable=False)
    act_number: Mapped[str] = mapped_column(Text, nullable=False)
    act_year: Mapped[int] = mapped_column(Integer, nullable=False)
    ministry: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'in_force'"))
    created_at: Mapped[datetime] = _now()

    provisions: Mapped[list[Provision]] = relationship(
        back_populates="act", cascade="all, delete-orphan"
    )
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="act", cascade="all, delete-orphan"
    )


class Provision(Base):
    """A node in the statutory tree for one Act (FR-CM-5).

    Attributes:
        id: Surrogate primary key.
        act_id: Owning Act (cascade on delete).
        parent_id: Parent provision in the tree, or ``None`` for top-level.
        kind: Node kind, one of :data:`PROVISION_KINDS`.
        number: Statutory identifier within the parent (e.g. ``103``, ``2a``).
        title: Optional heading text.
        sort_path: Slash-delimited path used for ordering (e.g. ``10/103/2``).
        act: The owning Act.
        parent: The parent provision.
        children: Direct child provisions.
        revisions: All temporal revisions of this provision.
        chunks: Chunks derived from this provision's revisions.
    """

    __tablename__ = "provisions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('part','chapter','section','subsection','clause')",
            name="provisions_kind_check",
        ),
        UniqueConstraint("act_id", "sort_path", name="provisions_act_id_sort_path_key"),
        Index("provisions_act_id", "act_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    act_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("acts.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provisions.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_path: Mapped[str] = mapped_column(Text, nullable=False)

    act: Mapped[Act] = relationship(back_populates="provisions")
    parent: Mapped[Provision | None] = relationship(
        back_populates="children", remote_side="Provision.id"
    )
    children: Mapped[list[Provision]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    revisions: Mapped[list[ProvisionRevision]] = relationship(
        back_populates="provision", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[Chunk]] = relationship(back_populates="provision")


class ProvisionRevision(Base):
    """A single temporal revision of a provision (ADR-006, FR-QR-6).

    Each section may have multiple revisions, each with its own effective window.
    Retrieval always filters against ``as_of_date`` using the composite index.

    Attributes:
        id: Surrogate primary key.
        provision_id: The provision this revision belongs to.
        language: ``bn`` (authoritative) or ``en`` (reference translation).
        translation_status: ``authoritative`` for Bengali; ``reference_translation``
            for the English text on bdlaws.
        text: Verbatim statutory text for this revision.
        effective_from: First date on which this revision was in force.
        effective_to: Last date on which this revision was in force; ``None``
            for currently-active revisions.
        amending_act_id: Act that introduced this revision, if annotated.
        content_hash: SHA-256 of the normalised text (change-detection, FR-IN-4).
        source_url: Canonical URL on bdlaws for this revision.
        fetched_at: When the revision was fetched.
        provision: The owning provision.
        amending_act: The Act that introduced this revision, if known.
        chunks: Chunks derived from this revision.
    """

    __tablename__ = "provision_revisions"
    __table_args__ = (
        CheckConstraint("language IN ('bn','en')", name="provision_revisions_language_check"),
        CheckConstraint(
            "translation_status IN ('authoritative','reference_translation')",
            name="provision_revisions_translation_status_check",
        ),
        Index(
            "provision_revisions_effective",
            "provision_id",
            "language",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    provision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provisions.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    translation_status: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    amending_act_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("acts.id"), nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = _now()

    provision: Mapped[Provision] = relationship(back_populates="revisions")
    amending_act: Mapped[Act | None] = relationship()
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="revision", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """An embedded, lexically indexed slice of a provision revision (FR-PR-3/5/6).

    ``act_id`` and ``language`` are denormalised for fast HNSW-filtered retrieval.
    ``hierarchy_path`` is materialised so it can be returned without joins.
    ``content_tsv`` uses the ``simple`` configuration because PostgreSQL ships no
    Bengali dictionary (ADR-007).

    Attributes:
        id: Surrogate primary key.
        revision_id: Owning provision revision.
        provision_id: Denormalised provision for fast scoped queries.
        act_id: Denormalised act for fast scoped HNSW queries.
        chunk_index: Position of the chunk within its revision.
        language: ``bn`` or ``en``.
        hierarchy_path: Full statutory breadcrumb prepended to embedded text.
        content: The chunk text.
        content_tsv: Generated lexical vector using the ``simple`` config (ADR-007).
        token_count: Token count of the chunk.
        embedding: Dense 1024-dim embedding vector (ADR-002).
        meta: Arbitrary chunk metadata (mapped from ``metadata`` column).
        created_at: Row creation timestamp.
        revision: The owning provision revision.
        provision: The owning provision.
        act: The owning Act.
    """

    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint("language IN ('bn','en')", name="chunks_language_check"),
        UniqueConstraint("revision_id", "chunk_index", name="chunks_revision_id_chunk_index_key"),
        Index(
            "chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": HNSW_OPS},
        ),
        Index("chunks_content_tsv_gin", "content_tsv", postgresql_using="gin"),
        Index("chunks_act_language", "act_id", "language"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provision_revisions.id", ondelete="CASCADE"), nullable=False
    )
    provision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provisions.id", ondelete="CASCADE"), nullable=False
    )
    act_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("acts.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    hierarchy_path: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 'simple' config — Bengali has no Postgres dictionary (ADR-007).
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', content)", persisted=True),
        nullable=False,
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(EMBED_DIMENSIONS), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _now()

    revision: Mapped[ProvisionRevision] = relationship(back_populates="chunks")
    provision: Mapped[Provision] = relationship(back_populates="chunks")
    act: Mapped[Act] = relationship()


class IngestionRun(Base):
    """A record of one ingestion attempt for a single (act, language) pair.

    Attributes:
        id: Surrogate primary key.
        act_id: The Act that was ingested.
        language: Language variant ingested (``bn`` or ``en``).
        status: Run status, one of :data:`RUN_STATUSES`.
        started_at: When the run started.
        finished_at: When the run finished, if it has.
        provisions_processed: Count of provisions handled in the run.
        chunks_created: Count of chunks produced in the run.
        error: Failure detail when ``status`` is ``"failed"``.
        act: The ingested Act.
    """

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint("language IN ('bn','en')", name="ingestion_runs_language_check"),
        CheckConstraint(
            "status IN ('running','succeeded','failed')",
            name="ingestion_runs_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    act_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("acts.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = _now()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provisions_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    chunks_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    act: Mapped[Act] = relationship(back_populates="ingestion_runs")


class Query(Base):
    """A logged query and its full observability record (architecture §4.3).

    ``disclaimer_version`` is NOT NULL: every response carries one, and we audit
    which version was active when the query was served (NFR-OB-3).

    Attributes:
        id: Surrogate primary key.
        correlation_id: Request-scoped tracing id.
        detected_language: Language detected from the query text.
        selected_language: Language used for response generation.
        act_ids: Acts retrieved for this query.
        as_of_date: Effective date used for retrieval filtering.
        query_text: The user question.
        retrieved_chunk_ids: Ordered ids of chunks supplied to generation.
        rerank_top_score: Top rerank score for the candidate set.
        declined: Whether the query was declined.
        decline_reason: Reason for declining, if declined.
        confidence_tier: Tier assigned to the response.
        degraded: Whether fail-open degraded mode was used.
        response_text: The generated answer, if any.
        provider: Provider that served the answer.
        prompt_version: Active prompt version used.
        disclaimer_version: Version of the disclaimer appended (NOT NULL).
        tokens_in: Prompt token count.
        tokens_out: Completion token count.
        cost_usd: Estimated request cost.
        cached: Whether the answer was served from cache.
        latency_ms: End-to-end latency in milliseconds.
        ip_hash: Hashed/truncated caller IP (NFR-SC-2).
        created_at: Row creation timestamp.
        feedback: Feedback entries bound to this query.
    """

    __tablename__ = "queries"
    __table_args__ = (
        CheckConstraint("detected_language IN ('bn','en')", name="queries_detected_language_check"),
        CheckConstraint("selected_language IN ('bn','en')", name="queries_selected_language_check"),
        CheckConstraint(
            "confidence_tier IN ('HIGH','MEDIUM','LOW')",
            name="queries_confidence_tier_check",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    act_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    )
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    )
    rerank_top_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    declined: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    degraded: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclaimer_version: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    cached: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _now()

    feedback: Mapped[list[Feedback]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )


class Feedback(Base):
    """User feedback bound to a logged query (FR-FB-1/2).

    Attributes:
        id: Surrogate primary key.
        query_id: The query this feedback concerns.
        rating: Feedback rating, one of :data:`FEEDBACK_RATINGS`.
        comment: Optional free-text comment.
        created_at: Row creation timestamp.
        query: The query this feedback concerns.
    """

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IN ('helpful','not_helpful','wrong_citation','out_of_scope')",
            name="feedback_rating_check",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _now()

    query: Mapped[Query] = relationship(back_populates="feedback")
