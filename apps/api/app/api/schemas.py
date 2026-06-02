"""Pydantic v2 request and response schemas for the public and admin API.

All endpoint I/O is typed through these models; SQLAlchemy ORM objects never
leave the service layer (architecture §2.6, NFR-MN-*).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

# ── Public request schemas ──────────────────────────────────────────────────


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


# ── Public response schemas ─────────────────────────────────────────────────


class QueryResponse(BaseModel):
    """Response to a successful query request.

    Attributes:
        query_id: UUID of the logged Query row (for submitting feedback).
        answer: Validated, disclaimer-bearing answer text.
        citations: Chunk IDs of the provisions cited in the answer.
        disclaimer: The active disclaimer text (also embedded in ``answer``).
        disclaimer_version: Version string of the active disclaimer.
        confidence: Retrieval confidence tier (``HIGH``, ``MEDIUM``, ``LOW``).
        cached: Whether the answer was served from the response cache.
        degraded: Whether fail-open mode was used (LLM/circuit-breaker).
        declined: Whether the decline gate fired (advice-seeking query).
        detected_language: Language detected from the query text.
        as_of_date: Effective date used for retrieval filtering.
    """

    query_id: str
    answer: str
    citations: list[str]
    disclaimer: str
    disclaimer_version: str
    confidence: str | None
    cached: bool
    degraded: bool
    declined: bool
    detected_language: str
    as_of_date: date | None


class FeedbackResponse(BaseModel):
    """Confirmation of stored feedback.

    Attributes:
        feedback_id: UUID of the created feedback row.
        query_id: UUID of the query this feedback concerns.
        rating: The submitted rating.
    """

    feedback_id: str
    query_id: str
    rating: str


class ThreadMessage(BaseModel):
    """One message in a playground thread (a logged Query row).

    Attributes:
        id: UUID of the Query row.
        question: The original query text.
        answer: The generated answer (may include disclaimer).
        disclaimer: Extracted disclaimer text, if available.
        declined: Whether the query was declined.
        cached: Whether the response was served from cache.
        degraded: Whether fail-open mode was used.
        confidence_tier: HIGH, MEDIUM, LOW, or None.
        detected_language: Language detected from the query.
        created_at: Timestamp the query was logged.
    """

    id: str
    question: str
    answer: str | None
    disclaimer: str | None
    declined: bool
    cached: bool
    degraded: bool
    confidence_tier: str | None
    detected_language: str | None
    created_at: datetime


class ThreadResponse(BaseModel):
    """All messages for a playground thread.

    Attributes:
        thread_id: The correlation ID / playground thread UUID.
        messages: Ordered list of query messages (oldest first).
    """

    thread_id: str
    messages: list[ThreadMessage]


class ThreadSummary(BaseModel):
    """Brief descriptor for one playground thread (list view).

    Attributes:
        thread_id: The correlation ID / playground thread UUID.
        first_question: The first question asked in this thread.
        message_count: Total number of messages in the thread.
        last_activity: Timestamp of the most recent message.
        detected_language: Language of the most recent message.
    """

    thread_id: str
    first_question: str
    message_count: int
    last_activity: datetime
    detected_language: str | None


class ThreadListResponse(BaseModel):
    """Paginated list of playground threads.

    Attributes:
        threads: Summaries ordered by last_activity descending.
        total: Total number of threads (before pagination).
    """

    threads: list[ThreadSummary]
    total: int


class ActSummary(BaseModel):
    """Brief Act descriptor for list responses.

    Attributes:
        id: UUID of the Act.
        slug: Operator-facing identifier.
        short_name: Display name.
        full_name_en: Official English title.
        full_name_bn: Official Bengali title.
        act_number: Roman-numeral act number.
        act_year: Year of enactment.
        status: Lifecycle status (``in_force``, ``partially_repealed``, ``repealed``).
        ministry: Responsible ministry, if known.
    """

    id: str
    slug: str
    short_name: str
    full_name_en: str
    full_name_bn: str
    act_number: str
    act_year: int
    status: str
    ministry: str | None


class ProvisionTreeNode(BaseModel):
    """One node in the statutory provision tree.

    Attributes:
        id: UUID of the provision.
        kind: Node kind (``part``, ``chapter``, ``section``, ``subsection``, ``clause``).
        number: Statutory number within the parent.
        title: Optional heading text.
        sort_path: Slash-delimited ordering path.
        children: Direct child nodes.
    """

    id: str
    kind: str
    number: str
    title: str | None
    sort_path: str
    children: list[ProvisionTreeNode]


ProvisionTreeNode.model_rebuild()


class ActStructure(BaseModel):
    """Full statutory tree for one Act.

    Attributes:
        act: Identifying Act metadata.
        tree: Root-level provision nodes.
    """

    act: ActSummary
    tree: list[ProvisionTreeNode]


class RevisionDetail(BaseModel):
    """One temporal revision of a provision.

    Attributes:
        language: Language variant (``bn`` or ``en``).
        translation_status: ``authoritative`` for Bengali; ``reference_translation`` for English.
        text: Verbatim statutory text.
        effective_from: First date on which this revision was in force.
        effective_to: Last date on which this revision was in force; ``None`` = current.
        source_url: Canonical URL on bdlaws.
    """

    language: str
    translation_status: str
    text: str
    effective_from: date
    effective_to: date | None
    source_url: str


class SectionDetail(BaseModel):
    """Full section detail with all revisions and the active disclaimer.

    Attributes:
        provision_id: UUID of the provision.
        act_slug: Slug of the owning Act.
        kind: Provision kind.
        number: Statutory number.
        title: Optional heading.
        hierarchy_path: Full statutory breadcrumb.
        revisions: All temporal revisions, all languages.
        disclaimer: Active disclaimer text (always present, NFR-LS-1).
    """

    provision_id: str
    act_slug: str
    kind: str
    number: str
    title: str | None
    hierarchy_path: str
    revisions: list[RevisionDetail]
    disclaimer: str


# ── Admin response schemas ──────────────────────────────────────────────────


class IngestionTriggerResponse(BaseModel):
    """Response to an ingestion trigger request.

    Attributes:
        task_ids: Celery task IDs dispatched.
        message: Human-readable confirmation.
    """

    task_ids: list[str]
    message: str


class IngestionRunSummary(BaseModel):
    """State of one ingestion run.

    Attributes:
        status: Run status (``running``, ``succeeded``, ``failed``).
        started_at: When the run started.
        finished_at: When the run finished, if it has.
        provisions_processed: Count of provisions handled.
        chunks_created: Count of chunks produced.
        error: Failure detail when failed.
    """

    status: str
    started_at: datetime
    finished_at: datetime | None
    provisions_processed: int
    chunks_created: int
    error: str | None


class AdminActSummary(BaseModel):
    """Act with ingestion state for the admin panel.

    Attributes:
        id: UUID of the Act.
        slug: Operator-facing identifier.
        short_name: Display name.
        full_name_en: Official English title.
        act_year: Year of enactment.
        status: Lifecycle status.
        last_run_bn: Latest ingestion run for Bengali.
        last_run_en: Latest ingestion run for English.
    """

    id: str
    slug: str
    short_name: str
    full_name_en: str
    act_year: int
    status: str
    last_run_bn: IngestionRunSummary | None
    last_run_en: IngestionRunSummary | None


class LLMOverrideRequest(BaseModel):
    """Request body for setting the LLM provider/model override.

    Attributes:
        provider: Provider name to activate.
        model: Model identifier for the provider.
    """

    provider: str = Field(pattern=r"^(anthropic|openai|ollama)$")
    model: str = Field(min_length=1)


class LLMOverrideResponse(BaseModel):
    """Current effective LLM configuration.

    Attributes:
        provider: Active provider name.
        model: Active model identifier.
        source: ``override`` when a Redis override is active; ``env`` otherwise.
    """

    provider: str
    model: str
    source: str


class ConfidenceBreakdown(BaseModel):
    """Count of queries per confidence tier in the metrics window.

    Attributes:
        HIGH: Queries with HIGH confidence.
        MEDIUM: Queries with MEDIUM confidence.
        LOW: Queries with LOW confidence.
    """

    HIGH: int
    MEDIUM: int
    LOW: int


class MetricsResponse(BaseModel):
    """Query quality and cost metrics over the last 24 hours.

    Attributes:
        total_queries: Total queries in the window.
        decline_rate: Fraction of queries declined.
        confidence_breakdown: Queries by confidence tier.
        cache_hit_rate: Fraction of queries served from cache.
        degraded_rate: Fraction of queries using fail-open mode.
        p95_latency_ms: 95th-percentile end-to-end latency in ms.
        daily_spend_usd: Summed estimated cost in the window.
        feedback_count: Feedback records created in the window.
    """

    total_queries: int
    decline_rate: float
    confidence_breakdown: ConfidenceBreakdown
    cache_hit_rate: float
    degraded_rate: float
    p95_latency_ms: float | None
    daily_spend_usd: float
    feedback_count: int


class RecentQuery(BaseModel):
    """Summary of one logged query for the admin feed.

    Attributes:
        id: UUID of the query.
        query_text: The user question (truncated to 200 chars).
        detected_language: Language detected from the query.
        declined: Whether the query was declined.
        confidence_tier: Retrieval confidence tier.
        cached: Whether served from cache.
        degraded: Whether fail-open mode was used.
        latency_ms: End-to-end latency in ms.
        created_at: Timestamp of the query.
    """

    id: str
    query_text: str
    detected_language: str | None
    declined: bool
    confidence_tier: str | None
    cached: bool
    degraded: bool
    latency_ms: int | None
    created_at: datetime


class RecentQueriesResponse(BaseModel):
    """Recent queries feed response.

    Attributes:
        queries: Most recent queries, ordered by created_at DESC.
        total: Total query count in the database.
    """

    queries: list[RecentQuery]
    total: int
