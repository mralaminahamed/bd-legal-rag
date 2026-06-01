# Architecture & Design

**Project:** Bangladesh Legal RAG (`bd-legal-rag`)
**Author:** Al Amin Ahamed ([@mralaminahamed](https://github.com/mralaminahamed))
**Document version:** 1.0
**Companion to:** `01-SRS.md`
**Last updated:** May 2026

---

## 1. Architectural Overview

The system is a self-hosted, asyncio-first Python service organised into six logical planes. The legal domain adds two planes that a general RAG would not have: a **safety plane** (disclaimer, decline, citation validation) and a **legal-domain processing plane** (statutory hierarchy preservation, effective-date filtering, canonical citation rendering). The five remaining planes mirror standard frameworkless RAG but are tuned for bilingual Bengali/English operation.

1. **Ingestion plane** — crawls `bdlaws.minlaw.gov.bd`, parses the statutory hierarchy, runs as Celery workers.
2. **Index plane** — PostgreSQL + pgvector holding Acts, provisions, chunks, embeddings, and the lexical index; full temporal model (effective dates, amendment chain).
3. **Retrieval plane** — language detection, hybrid search with mandatory cross-encoder rerank, effective-date filtering.
4. **Generation plane** — provider-agnostic LLM driver, versioned prompt registry, response cache, cost circuit breaker.
5. **Safety plane** — decline gate, citation validator, disclaimer injector, normative-conclusion guard.
6. **Delivery plane** — FastAPI service and a bilingual search-style web interface.

Two architectural commitments shape everything:

- **The disclaimer is application-controlled, never model-controlled.** It is appended to every user-facing response by `app/rag/generator.py` regardless of model output. The LLM cannot omit, rewrite, or move it.
- **The citation is the answer.** A correct plain-language summary with the wrong citation is a failure. The eval suite is weighted accordingly.

### 1.1 System Context

```
            ┌──────────────────────────────────────────────────────────────┐
            │                        Hetzner host                           │
            │                                                                │
  End user ─┼─▶ Caddy ─▶ FastAPI ──▶ LangRouter ──▶ Retriever ──▶ Reranker ─┼─▶ Cohere (embed + rerank)
            │                              │              │          │       │
            │                              ▼              ▼          ▼       │
            │                       PostgreSQL      Redis (cache,  Decline   │
            │                       + pgvector       broker, rate)  Gate     │
            │                                                       │       │
            │                       Celery workers ──crawl──────────┼──────┬─┼─▶ bdlaws.minlaw.gov.bd
            │                                                       ▼      ▼ │
            │                                                 Generator → Anthropic / OpenAI / Ollama
            │                                                       │       │
            │                                                 Disclaimer    │
            │                                                 Injector      │
            └──────────────────────────────────────────────────────────────┘
```

### 1.2 Request Lifecycle (cache-miss query)

```
1.  POST /api/v1/query  { question, act_slug?, language?, as_of_date? }
2.  Validate (Pydantic v2), assign correlation id, per-IP rate limit.
3.  LangRouter: if language=auto, detect (Bangla Unicode block vs Latin); fall back to mixed-script heuristic.
4.  Cache lookup: hash(normalised_query | act_scope | as_of_date | model | prompt_version | reranker_version).
    Hit  → 7.  Miss → continue.
5.  Retrieve:
      a. Embed query (input_type=search_query) with embed-multilingual-v3.0.
      b. Vector top-N via HNSW on the language-matching column, scoped by act_id and effective dates.
      c. Lexical top-N via tsvector with the simple configuration (Bengali-tolerant).
      d. Reciprocal Rank Fusion → candidate set.
      e. Cross-lingual fallback: if RRF top score < cross_lingual_floor, repeat (a-d) on the
         opposite-language index and merge.
      f. Mandatory rerank with rerank-multilingual-v3.0 → top_k.
      g. Effective-date filter against as_of_date (default = today).
6.  Decline gate: classify the query (advice_seeking | out_of_scope | informational).
    If advice_seeking OR retrieval recall < decline_floor → take decline path (skip step 7-8 of generation;
    proceed straight to step 9 with decline_response).
7.  Confidence tier = f(rerank_score_distribution, recall_signal, language_coverage).
8.  Generate:
      a. Resolve active prompt version from app/prompts/registry.
      b. Build prompt: fenced question + fenced provisions (verbatim + canonical citations).
      c. Cost pre-check; circuit breaker arms.
      d. Provider call via driver (timeout + bounded retry + backoff).
         - Failure → fail-open: skip summary; emit retrieved provisions only.
      e. Citation validator: strip any citation that does not map to a supplied chunk.
      f. Normative-conclusion guard: scan output for blacklisted normative phrases (per
         NFR-LS-2) in BN and EN; reject and retry once with a stricter system prompt.
9.  Disclaimer injector appends the active disclaimer (BN + EN as appropriate).
10. Cache response. Log query record. Stream/return.
```

---

## 2. Component Design

### 2.1 Module Layout

```
bd-legal-rag/                         # monorepo root (Turborepo + pnpm)
├── apps/
│   ├── api/                          # Python FastAPI service
│   │   ├── app/
│   │   │   ├── main.py               # FastAPI factory, lifespan, routers
│   │   │   ├── config.py             # pydantic-settings; all tunables
│   │   │   ├── db/
│   │   │   │   ├── engine.py
│   │   │   │   ├── models.py         # SQLAlchemy 2.0 declarative
│   │   │   │   ├── redis.py          # async Redis client singleton
│   │   │   │   └── migrations/       # Alembic
│   │   │   ├── ingestion/
│   │   │   │   ├── registry.py       # Act + source CRUD; declarative loader
│   │   │   │   ├── crawler.py        # bdlaws fetch + polite throttling
│   │   │   │   ├── parser.py         # HTML → statutory parse tree
│   │   │   │   ├── normalize.py      # sanitise; preserve hierarchy
│   │   │   │   ├── amendments.py     # amendment chain detection
│   │   │   │   ├── summary.py        # IngestSummary model (task output)
│   │   │   │   └── tasks.py          # Celery tasks per (act, language)
│   │   │   ├── processing/
│   │   │   │   ├── chunker.py        # section-hierarchy-aware
│   │   │   │   └── embedder.py       # Cohere multilingual; input_type asymmetry
│   │   │   ├── rag/
│   │   │   │   ├── lang_router.py    # script + heuristic detection
│   │   │   │   ├── retriever.py      # vector_search, lexical_search, _fuse,
│   │   │   │   │                     #   hybrid_retrieve; as_of filter
│   │   │   │   ├── reranker.py       # Cohere rerank-multilingual (mandatory)
│   │   │   │   ├── service.py        # retrieval entry point: route → embed →
│   │   │   │   │                     #   retrieve → rerank; used by eval + API
│   │   │   │   ├── decline_gate.py   # advice-seeking + recall floor classifier
│   │   │   │   ├── confidence.py     # tiering from rerank + recall + coverage
│   │   │   │   ├── citation.py       # canonical formatter (BN/EN)
│   │   │   │   ├── generator.py      # orchestration; streaming; validator;
│   │   │   │   │                     #   guardrails; disclaimer injector
│   │   │   │   └── guardrails.py     # normative-conclusion phrase guard
│   │   │   ├── llm/
│   │   │   │   ├── base.py           # LLMProvider + StreamingProvider protocols
│   │   │   │   ├── anthropic.py
│   │   │   │   ├── openai.py
│   │   │   │   ├── ollama.py
│   │   │   │   ├── factory.py
│   │   │   │   ├── runtime.py        # Redis-based provider/model override
│   │   │   │   ├── circuit_breaker.py
│   │   │   │   └── cache.py
│   │   │   ├── prompts/
│   │   │   │   ├── registry.py
│   │   │   │   ├── families/
│   │   │   │   │   └── legal_answer/ # versioned prompt definitions
│   │   │   │   └── safety/
│   │   │   │       ├── disclaimer.py # versioned EN + BN text
│   │   │   │       └── decline.py    # versioned EN + BN text
│   │   │   ├── api/
│   │   │   │   ├── routes_query.py
│   │   │   │   ├── routes_browse.py  # faceted Act → Chapter → Section
│   │   │   │   ├── routes_admin.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── deps.py
│   │   │   └── observability/logging.py
│   │   ├── eval/
│   │   │   ├── dataset/golden.jsonl
│   │   │   ├── runs/                 # eval run artefacts (gitignored)
│   │   │   ├── harness.py
│   │   │   └── metrics.py
│   │   ├── tests/                    # mirrors app/; all external calls mocked
│   │   ├── scripts/                  # one-off admin scripts (sync_acts.py etc.)
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── admin/                        # React/TypeScript operator dashboard
│   │   ├── src/
│   │   │   ├── api/                  # axios client + typed API helpers
│   │   │   ├── app/routes.tsx
│   │   │   ├── components/{layout,ui}/
│   │   │   ├── features/             # RegisterActModal, SourcesRow
│   │   │   ├── hooks/
│   │   │   ├── lib/
│   │   │   ├── pages/                # DashboardPage, PlaygroundPage,
│   │   │   │                         #   ActsPage, SettingsPage
│   │   │   ├── styles/globals.css
│   │   │   └── types/api.ts
│   │   ├── e2e/                      # Playwright end-to-end tests
│   │   ├── Dockerfile
│   │   └── package.json
│   └── web/                          # bilingual search-style web interface
│       └── index.html
├── caddy/
│   └── Caddyfile                     # TLS reverse proxy for production
├── config/
│   └── acts/                         # declarative Act YAML registration
│       ├── companies-act-1994.yaml
│       ├── income-tax-act-2023.yaml
│       ├── vat-sd-act-2012.yaml
│       ├── labour-act-2006.yaml
│       └── digital-security-act-2018.yaml
├── docs/                             # authoritative specs (SRS, Architecture, etc.)
├── docker-compose.yml
├── docker-compose.prod.yml
├── package.json                      # monorepo root (Turborepo)
├── pnpm-workspace.yaml
├── turbo.json
├── .env.example
└── CLAUDE.md
```

### 2.2 Ingestion

**Crawler.** `app/ingestion/crawler.py` retrieves Act pages from `bdlaws.minlaw.gov.bd` for both languages. A configured request-rate ceiling and `Retry-After` handling protect the source. ETag/Last-Modified handling minimises load on re-runs.

**Parser.** `app/ingestion/parser.py` walks the page DOM and emits a typed parse tree:

```python
@dataclass(frozen=True)
class ProvisionNode:
    """A node in the statutory parse tree extracted from a bdlaws page.

    Attributes:
        kind: One of "act", "part", "chapter", "section", "subsection", "clause".
        number: Statutory identifier within its parent (e.g. "103", "2", "a").
        title: Optional heading text.
        text: Verbatim provision text; empty for container nodes.
        children: Ordered child provisions.
        effective_from: Earliest known effective date (may be None).
        effective_to: Latest known effective date if superseded (may be None).
        source_url: Canonical URL on the portal.
    """

    kind: Literal["act", "part", "chapter", "section", "subsection", "clause"]
    number: str
    title: str | None
    text: str
    children: tuple["ProvisionNode", ...]
    effective_from: date | None
    effective_to: date | None
    source_url: str
```

**Amendment detection.** `app/ingestion/amendments.py` parses the portal's inline amendment annotations where present and records the amending Act and date. Where the portal does not annotate, the provision is recorded with `effective_from = as_of` (the crawl date) and a `provenance` of `"snapshot"` so users understand the temporal coverage limit.

**Tasks.** One Celery task per `(act, language)`. A failed task records the error on its `ingestion_runs` row and is independently retryable. Sibling tasks proceed regardless.

**IngestSummary.** Each task returns an `IngestSummary` (from `app/ingestion/summary.py`) that the admin API surfaces:

```python
class IngestSummary(BaseModel):
    act_id: uuid.UUID
    language: Literal["bn", "en"]
    status: Literal["succeeded", "failed"]
    provisions_new: int
    provisions_updated: int
    provisions_unchanged: int   # skipped by content hash
    chunks_created: int
    error: str | None
```

The `provisions_unchanged` count is the primary indicator of incremental re-ingest efficiency: a full run that changes nothing should report zero `provisions_updated` and zero `chunks_created`.

### 2.3 Processing

**Section-hierarchy-aware chunking.** Each chunk corresponds to a leaf provision (subsection or clause where present; otherwise section). Oversized provisions (rare; very long sections in tax law) are split at paragraph boundaries with a small overlap.

Critically, every chunk text is **prepended with its hierarchical path**:

```
Bangladesh Labour Act, 2006 > Chapter X > Section 103 (Weekly holiday)
[provision text]
```

This single design choice (carried forward from the author's earlier work on legal RAG edit distance) materially improves retrieval precision and gives the model an unambiguous citation handle.

**Embedding.** `embed-multilingual-v3.0` distinguishes `input_type` for documents vs queries; this asymmetry is non-optional and is enforced at the type level:

```python
class EmbedInputType(StrEnum):
    """Cohere input_type discriminator.

    Documents are embedded at ingest time; queries at request time. Passing the
    wrong type silently degrades retrieval quality, so the embedder forbids it.
    """

    SEARCH_DOCUMENT = "search_document"
    SEARCH_QUERY = "search_query"
```

Embeddings are written in 1024 dimensions to `vector(1024)` with an HNSW cosine index.

### 2.4 Retrieval

**Language router.** Detection uses Unicode-block analysis (Bengali block U+0980–U+09FF coverage ratio) with a fallback `langid`-style classifier for mixed-script queries. The detected language scopes the primary retrieval index; the opposite-language index is queried as a fallback when RRF top scores fall below `cross_lingual_floor` (FR-QR-3).

**Retrieval service.** `app/rag/service.py` is the single entry point for the retrieval pipeline. It ties language routing, query embedding, hybrid retrieval, and mandatory reranking into one call consumed by the eval harness, the test suite, and the generation path. Separating retrieval orchestration from generation lets the eval harness test retrieval precision independently of generation cost.

```python
@dataclass
class RetrievalResult:
    query: str
    detected_language: Literal["bn", "en", "mixed"]
    act_ids: list[uuid.UUID]        # scope applied
    cross_lingual: bool             # fallback engaged
    chunks: list[RetrievedChunk]
    reranked: bool
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    as_of_date: date
```

**Hybrid retriever (`retriever.py`).** Exposes composable sub-functions so each stage is independently testable:

- `vector_search(session, embedding, act_ids, language, as_of_date, settings) → list[_Hit]` — HNSW cosine, scoped by act and language, with the effective-date predicate always applied.
- `lexical_search(session, query, act_ids, language, as_of_date, settings) → list[_Hit]` — `websearch_to_tsquery` over `content_tsv` (built with the `simple` configuration — ADR-007), `ts_rank_cd` ordering, effective-date predicate always applied.
- `_fuse(vector_hits, lexical_hits, settings) → list[RetrievedChunk]` — Reciprocal Rank Fusion with configurable per-list weights; lexical matches always survive the minimum-score threshold; vector-only hits must clear `similarity_threshold`.
- `hybrid_retrieve(session, query, embedding, act_ids, language, as_of_date, settings) → list[RetrievedChunk]` — orchestrates the three functions above; each signal is skipped when its weight is zero, keeping the other signal usable.

Two legal-domain specialisations are applied in both `vector_search` and `lexical_search`:

- **Effective-date filter.** `WHERE effective_from ≤ :as_of_date AND (effective_to IS NULL OR effective_to ≥ :as_of_date)`. Default `as_of_date` is today. Never omitted.
- **Lexical tokenisation tolerant of Bengali.** The `tsvector` uses the `simple` configuration (Bengali has no Postgres dictionary). Lexical recall on Bengali is weaker than vector recall by design, but it contributes for Latin transliterations and exact numeric references (section numbers, dates).

**Mandatory rerank.** `rerank-multilingual-v3.0` reorders the fused candidate set. In this system rerank is not a configurable optimisation — it is a structural requirement (FR-QR-5) because legal precision demands it. When the reranker is unreachable, the system surfaces `LOW` confidence and returns the unreranked top set rather than failing the request (NFR-RL-2).

### 2.5 Generation, Safety, and Citation

**Generator pipeline** (fixed order, no skip allowed):

```
cache.get
  → decline_gate.classify
      → if decline → decline_response  ──┐
  → confidence.tier                       │
  → circuit_breaker.guard                 │
  → provider.complete  (or .stream)       │
      → on ProviderUnavailable → fail-open (provisions only, no summary)
  → citation.validate (strip foreign placeholders)
  → guardrails.scan (normative phrases)   │
      → on violation: one retry with stricter system prompt
  → disclaimer.inject  ◀───────────────────┘
  → cache.set
```

**Streaming generation.** `generator.py` exposes two top-level callables: `generate()` (returning a complete `GenerationResult`) and `generate_stream()` (yielding `StreamEvent` objects). Both share the same fixed pipeline — citation validation, guardrails, and disclaimer injection happen before the final event is emitted, not while tokens flow. Providers that support streaming implement `StreamingProvider` in addition to `LLMProvider`; the generator detects this at runtime and falls back to `complete()` for non-streaming providers.

```python
class StreamEvent(BaseModel):
    type: Literal["token", "final"]
    text: str = ""                      # delta for type=="token"
    answer: str | None = None           # validated answer for type=="final"
    citations: list[str] = []           # canonical citation strings
    cached: bool = False
    degraded: bool = False
    declined: bool = False
    disclaimer: str | None = None       # active disclaimer (on "final" only)
    usage: TokenUsage | None = None
```

The `final` event always carries the validated, disclaimer-bearing answer so the client can replace the streamed provisional text. The provisional stream (token events) omits the disclaimer; it is present only on the `final` event, consistent with NFR-LS-1.

The cost circuit breaker tracks running output tokens mid-stream and aborts an overrun before more cost accrues.

**Decline gate.** A small classifier (keyword + pattern + LLM-free heuristic in v1) flags advice-seeking queries. Examples (English): "should I…", "what should I do if…", "is it legal for me to…", "can I sue…". Bengali patterns are mirrored. The gate also fires when retrieval recall is below a configured floor (the corpus simply has no answer). The decline response is canonical, multilingual, and version-controlled in `app/prompts/safety/decline.py`.

**Confidence tier.**

| Tier | Conditions |
|---|---|
| `HIGH` | Rerank top score ≥ `t_high` AND ≥ 2 chunks above `t_keep` AND single-Act coverage. |
| `MEDIUM` | Rerank top score ≥ `t_medium` OR multi-Act coverage with strong single top. |
| `LOW` | Reranker unreachable (NFR-RL-2), or rerank top score < `t_medium`, or cross-lingual fallback engaged. |

**Citation formatter.** Canonical forms (FR-GN-2):

- English: `Section 103(2) of the Bangladesh Labour Act, 2006`
- Bengali: `বাংলাদেশ শ্রম আইন, ২০০৬-এর ধারা ১০৩(২)`

The formatter resolves Act name in the response language and renders Bengali numerals when the response language is Bengali (per Unicode digit conversion). It is the single source of truth for citation strings; the LLM is told to use `{{cite:chunk_id}}` placeholders, which the formatter replaces post hoc.

**Normative-conclusion guard.** `app/rag/guardrails.py` scans model output against a versioned, bilingual blacklist (e.g. EN: `you must`, `you cannot`, `it is illegal`; BN: `আপনাকে অবশ্যই`, `আপনি পারবেন না`, `এটি অবৈধ`). One retry is allowed with a stricter system prompt; on second violation, the system falls back to fail-open output (provisions + citations + disclaimer, no summary). Patterns are tunable; updates are reviewed alongside eval results.

**Disclaimer injector.** `app/prompts/safety/disclaimer.py` exposes a versioned `Disclaimer` with `bn` and `en` text. `app/rag/generator.py` appends the appropriate variant(s) to every user-facing response — including cache-hits, decline responses, and fail-open responses. There is no path that bypasses the injector. The disclaimer version that accompanied each response is logged with the query (NFR-OB-3).

### 2.6 Prompt Registry

Identical mechanism to a general RAG: families of immutable versioned prompts under `app/prompts/families/`, with the active version resolved at runtime. The initial family is `legal_answer` with one active version. The render function:

- Places the question in a fenced, labelled, non-instructional block.
- Places each retrieved provision in its own fenced block, prefixed with `{{cite:chunk_id}}` so the citation formatter can resolve placeholders.
- Includes explicit instructions to attribute every normative statement and to never assert a legal conclusion.

The disclaimer is **not** in the prompt. It is applied by the application after generation.

---

## 3. Data Model

### 3.1 Entity Relationships

```
acts (1) ──< (N) provisions (1) ──< (N) chunks
acts (1) ──< (N) amendments
provisions (1) ──< (N) provision_revisions   (effective_from / effective_to)
acts (1) ──< (N) ingestion_runs              (per language)
acts (1) ──< (N) queries (1) ──< (N) feedback
```

### 3.2 Schema (PostgreSQL + pgvector)

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Acts
CREATE TABLE acts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          text NOT NULL UNIQUE,                   -- e.g. "labour-act-2006"
    short_name    text NOT NULL,                          -- "Labour Act 2006"
    full_name_en  text NOT NULL,
    full_name_bn  text NOT NULL,
    act_number    text NOT NULL,                          -- "XLII"
    act_year      int  NOT NULL,
    ministry      text,
    status        text NOT NULL DEFAULT 'in_force'
                  CHECK (status IN ('in_force','partially_repealed','repealed')),
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Provisions (the statutory tree)
CREATE TABLE provisions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    act_id          uuid NOT NULL REFERENCES acts(id) ON DELETE CASCADE,
    parent_id       uuid REFERENCES provisions(id) ON DELETE CASCADE,
    kind            text NOT NULL CHECK (kind IN ('part','chapter','section','subsection','clause')),
    number          text NOT NULL,                        -- "103", "2", "a"
    title           text,
    sort_path       text NOT NULL,                        -- "10/103/2" for ordering
    UNIQUE (act_id, sort_path)
);
CREATE INDEX provisions_act_id ON provisions (act_id);

-- Provision revisions (temporal model)
CREATE TABLE provision_revisions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provision_id   uuid NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
    language       text NOT NULL CHECK (language IN ('bn','en')),
    translation_status text NOT NULL
                       CHECK (translation_status IN ('authoritative','reference_translation')),
    text           text NOT NULL,
    effective_from date NOT NULL,
    effective_to   date,
    amending_act_id uuid REFERENCES acts(id),
    content_hash   text NOT NULL,
    source_url     text NOT NULL,
    fetched_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX provision_revisions_effective
    ON provision_revisions (provision_id, language, effective_from, effective_to);

-- Chunks (one per provision_revision after chunking)
CREATE TABLE chunks (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id     uuid NOT NULL REFERENCES provision_revisions(id) ON DELETE CASCADE,
    provision_id    uuid NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
    act_id          uuid NOT NULL REFERENCES acts(id) ON DELETE CASCADE,
    chunk_index     int  NOT NULL,
    language        text NOT NULL CHECK (language IN ('bn','en')),
    hierarchy_path  text NOT NULL,                        -- "Act > Chapter X > Section 103"
    content         text NOT NULL,
    content_tsv     tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    token_count     int NOT NULL,
    embedding       vector(1024) NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (revision_id, chunk_index)
);

CREATE INDEX chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX chunks_content_tsv_gin ON chunks USING gin (content_tsv);
CREATE INDEX chunks_act_language    ON chunks (act_id, language);

-- Ingestion runs
CREATE TABLE ingestion_runs (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    act_id               uuid NOT NULL REFERENCES acts(id) ON DELETE CASCADE,
    language             text NOT NULL CHECK (language IN ('bn','en')),
    status               text NOT NULL CHECK (status IN ('running','succeeded','failed')),
    started_at           timestamptz NOT NULL DEFAULT now(),
    finished_at          timestamptz,
    provisions_processed int NOT NULL DEFAULT 0,
    chunks_created       int NOT NULL DEFAULT 0,
    error                text
);

-- Queries (logging)
CREATE TABLE queries (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id      text NOT NULL,
    detected_language   text CHECK (detected_language IN ('bn','en')),
    selected_language   text CHECK (selected_language IN ('bn','en')),
    act_ids             uuid[] NOT NULL DEFAULT '{}',
    as_of_date          date,
    query_text          text NOT NULL,
    retrieved_chunk_ids uuid[] NOT NULL DEFAULT '{}',
    rerank_top_score    numeric(6,4),
    declined            boolean NOT NULL DEFAULT false,
    decline_reason      text,
    confidence_tier     text CHECK (confidence_tier IN ('HIGH','MEDIUM','LOW')),
    degraded            boolean NOT NULL DEFAULT false,
    response_text       text,
    provider            text,
    prompt_version      text,
    disclaimer_version  text NOT NULL,
    tokens_in           int,
    tokens_out          int,
    cost_usd            numeric(10,6),
    cached              boolean NOT NULL DEFAULT false,
    latency_ms          int,
    ip_hash             text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Feedback
CREATE TABLE feedback (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id   uuid NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    rating     text NOT NULL CHECK (rating IN ('helpful','not_helpful','wrong_citation','out_of_scope')),
    comment    text,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

Notes:

- `provision_revisions` is the temporal model: a single section may have multiple revisions over time, each with its own effective window. Retrieval joins through this table when an `as_of_date` is supplied.
- `chunks` denormalises `act_id` and `language` for fast filtered HNSW retrieval; `hierarchy_path` is materialised so it can be returned without joins.
- The `disclaimer_version` column on `queries` is mandatory (NOT NULL): every response carries one, and we audit which version did.

---

## 4. Cross-Cutting Concerns

### 4.1 Configuration

A single `pydantic-settings` `Settings` object exposes every tunable: database/Redis DSNs, provider keys (Cohere, Anthropic, OpenAI, Ollama base URL), default LLM provider, embedding model and `input_type` enforcement, chunking parameters, retrieval `top_k`/`top_n`/`rrf_k`/`ef_search`/`cross_lingual_floor`, decline thresholds, confidence thresholds (`t_high`, `t_medium`, `t_keep`), cost ceiling, rate-limit windows, and the active disclaimer/decline versions. No behavioural constant is hard-coded (NFR-MN-4).

### 4.2 Security

- Untrusted query text is length-bounded and fenced in clearly delimited, non-instructional blocks; retrieved content is similarly fenced (NFR-SC-3).
- Ingested HTML is sanitised before storage; preserved-original HTML is stored separately and never injected into prompts (NFR-SC-4).
- Admin endpoints are bearer-authenticated; public endpoints rate-limited per hashed IP (NFR-SC-2).
- Secrets are environment-only and redacted from all logs (NFR-SC-1).

### 4.3 Observability

Every request carries a correlation id. Structured logs capture detected and selected language, `act_ids` retrieved, `as_of_date`, rerank top score, decline flag and reason, confidence tier, degraded flag, latency, token counts, cost, cache-hit, and disclaimer version. Eval-runtime captures the same fields plus per-Act/per-language metrics.

### 4.4 Fail-Open Strategy

There are two distinct degradation modes:

1. **LLM unreachable** (NFR-RL-1) → emit retrieved provisions, canonical citations, and the disclaimer. No summary. Mark `degraded=true`.
2. **Reranker unreachable** (NFR-RL-2) → proceed with the fused (unreranked) candidates, downgrade confidence to `LOW`, still summarise.

Both paths still invoke the disclaimer injector. Neither path bypasses citation validation.

---

## 5. Architecture Decision Records (abridged)

### ADR-001 — Frameworkless RAG over LangChain/LlamaIndex
**Decision:** Direct pgvector + provider SDKs. Same rationale as the author's other RAG work.
**Consequence:** Explicit control over chunking, fusion, rerank, citation, and safety — all of which the eval suite must pin.

### ADR-002 — Cohere `embed-multilingual-v3.0` at 1024 dimensions
**Decision:** Use Cohere's multilingual model with `vector(1024)` and the documented `input_type` asymmetry.
**Rationale:** A truly multilingual model is required for the Bengali corpus; `embed-multilingual-v3.0` is currently the strongest production option that exposes the `search_document`/`search_query` discriminator. 1024 dims sits comfortably under pgvector's HNSW limit, avoiding the `halfvec` complication.
**Consequence:** The embedder must enforce `input_type` at the type level; mixing them silently halves retrieval quality.

### ADR-003 — Mandatory cross-encoder rerank
**Decision:** `rerank-multilingual-v3.0` is a required stage, not an optimisation.
**Rationale:** Legal questions reward precision over recall. The fused candidate set is broad; a cross-encoder is the cheapest reliable way to push the right section to top-1.
**Consequence:** When the reranker is unreachable, the system degrades (LOW confidence) rather than failing — but rerank is structurally part of the pipeline (NFR-RL-2 vs NFR-RL-1 differ).

### ADR-004 — Application-controlled disclaimer
**Decision:** The disclaimer is appended by `app/rag/generator.py`, not generated by the LLM.
**Rationale:** The LLM cannot be relied upon to include the disclaimer verbatim, in the correct language, on every response — including cache-hits, decline responses, fail-open responses, and errors. Treating it as application output eliminates that risk class entirely.
**Consequence:** The disclaimer is version-controlled in `app/prompts/safety/disclaimer.py`, logged per query, and never inside the prompt context window.

### ADR-005 — Citation as placeholder + post hoc resolver
**Decision:** The LLM emits `{{cite:chunk_id}}` placeholders; `app/rag/citation.py` resolves them to canonical bilingual citation strings.
**Rationale:** Citation formatting is rule-based and the rules differ by language (Latin vs Bengali numerals, English vs Bengali Act names). Asking the model to format citations introduces avoidable variation; resolving post hoc guarantees canonical form and makes citation-accuracy testable independently of model quality.
**Consequence:** The citation validator can verify with `set` operations rather than NLP. Any placeholder the model emits whose chunk id is not in the supplied set is stripped.

### ADR-006 — Effective-date filtering at query time
**Decision:** Filter retrieved chunks by `as_of_date` against `provision_revisions.effective_from`/`effective_to` (default `today`).
**Rationale:** Statute law is temporal. A user asking about the 2018 form of a provision must not receive the 2024 amended text.
**Consequence:** Retrieval queries always include the effective-date predicate; the index supports it via the composite index on `(provision_id, language, effective_from, effective_to)`.

### ADR-008 — Runtime provider/model override via Redis

**Decision:** `app/llm/runtime.py` reads a Redis key `llm:override` containing a JSON `{provider, model}` pair. When present and valid, this overrides the env-file defaults for the active generation provider and model without a restart. The admin endpoint exposes `GET/PUT/DELETE /admin/llm/override`.

**Rationale:** Switching providers during an incident (e.g. Anthropic outage → OpenAI fallback) currently requires an env edit and restart. A Redis override is visible to the operator in real time, reverts cleanly on `DELETE`, and falls back to the env defaults when the key is absent or malformed — so a stale or invalid override can never wedge generation.

**Consequence:** The admin `routes_admin.py` gains three endpoints for the override. The factory resolves provider via `runtime.resolve(redis, settings)` rather than reading settings directly. Tests mock Redis.

---

### ADR-007 — Bengali lexical tokenisation via `simple` configuration
**Decision:** Use the `simple` PostgreSQL text-search configuration for `content_tsv`.
**Rationale:** Postgres ships no Bengali dictionary. The `simple` configuration tokenises on whitespace and lowercase folds — adequate for hybrid recall on Latin transliterations, section numbers, and exact terms. Vector retrieval carries the semantic load on Bengali.
**Consequence:** Lexical contribution to RRF is asymmetric across languages; thresholds are tuned per language.

---

## 6. Capacity and Cost Notes

The v1.0 corpus (five Acts, two languages) is small in absolute terms — on the order of low tens of thousands of chunks. Embedding cost is dominated by the one-time ingest; content-hash skip prevents repeat embeds. Generation cost is bounded per request by the circuit breaker and amortised by the response cache, whose hit rate rises quickly for popular sections (employment hours, VAT thresholds, common Companies Act questions). Rerank is the largest per-query cost; configuring the candidate set conservatively (`top_n` ~50) keeps it bounded.

---

*Authored by Al Amin Ahamed. This document realises the requirements in `01-SRS.md` and is implemented per `03-Implementation-Plan.md`.*
