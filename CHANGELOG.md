# Changelog

All notable changes to bd-legal-rag are documented here.

---

## [Unreleased]

### Added
- 11 additional high-priority Acts: Penal Code 1860, Evidence Act 1872, Contract Act 1872,
  Specific Relief Act 1877, Negotiable Instruments Act 1881, Transfer of Property Act 1882,
  Code of Criminal Procedure 1898, Code of Civil Procedure 1908, Limitation Act 1908,
  Partnership Act 1932, Constitution of Bangladesh 1972 (16 Acts total)
- Ollama embedding fallback via `qwen3-embedding:4b` (2560-dim `halfvec`) — no Cohere key
  required for local development
- Chat threading in Playground: each conversation gets a UUID sub-route (`/playground/:threadId`),
  messages persist in `localStorage`, "New chat" navigates to a fresh UUID
- Sub-route routing: `/playground` redirects to `/playground/:uuid` on every visit
- `OllamaEmbedder` in `processing/embedder.py` — uses sync `httpx.Client` via
  `run_in_executor` to avoid event-loop inheritance issues in Celery ForkPoolWorker
- `halfvec(2560)` migration replacing `vector(1024)` — pgvector 0.7+ halfvec supports
  HNSW up to 4000 dims; `halfvec_cosine_ops` operator class
- Laravel-style seeder system (`app/seeders/`): `acts`, `corpus`, `ingestion_runs`,
  `queries`, `feedback` — 60 bilingual chunks, 20 sample queries, 16 feedback rows
- Admin bearer token auto-seeded from `VITE_ADMIN_TOKEN` build arg — no manual Settings
  entry needed in development
- `favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, OG image
  (1200×630), `site.webmanifest`; theme-color responsive to `prefers-color-scheme`
- Full UI redesign: wp-support-rag design system — CVA components, `oklch` primary,
  `halfvec_cosine_ops` cards, `Geist Variable` font, collapsible dark navy sidebar,
  `max-w-[1100px]` content constraint, `backdrop-blur` top bar, proper dark mode

### Fixed
- `BDRAG_OLLAMA_BASE_URL=http://localhost:11434` in `.env` was passed into Docker
  containers where `localhost` resolves to the container, not the host; removed so
  Docker Compose falls back to `http://host.docker.internal:11434`
- `httpx.AsyncClient` in Celery ForkPoolWorker fails due to inherited event-loop state
  from the parent process; switched to sync `httpx.Client` via `run_in_executor`
- `python -m app.ingestion.registry bootstrap` silently ignored `sys.argv` (no `__main__`
  block); added entry point that calls `bootstrap()` and prints a summary
- `decline_recall_floor=0.10` always declined queries — RRF scores max ~0.025; set to
  `0.001` in `.env` and `docker-compose.yml`
- Lexical search matched only `content` column; added `hierarchy_path` OR-word fallback
  so queries like "weekly holiday Labour Act" match via chapter/section titles
- `config.py` `Path(__file__).parents[3]` raised `IndexError` inside Docker (shallower
  path); guarded with `try/except IndexError`
- `IndexError: parents[3]` in Docker — guarded with try/except
- Native `<dialog>` lost `margin: auto` from Tailwind preflight; added `m-auto`, backdrop
  click-to-close, body scroll lock, entrance animation

---

## [0.1.0] — 2026-05-31

First working release. All phases complete.

### Phase 0 — Project scaffold
- Monorepo layout: `apps/api/`, `apps/web/`, `config/acts/`, `docs/`, `eval/`
- `docker-compose.yml` with PostgreSQL (pgvector), Redis, FastAPI, Celery worker/beat,
  nginx-served React admin console
- Pydantic-settings configuration (`BDRAG_` prefix, repo-root `.env`)
- SQLAlchemy 2.0 async engine with `lru_cache` session factory

### Phase 1 — Database schema
- `acts`, `provisions`, `provision_revisions`, `chunks`, `ingestion_runs`, `queries`,
  `feedback` tables with CHECK constraints and unique indices
- `vector(1024)` embedding column with HNSW index (`vector_cosine_ops`, m=16,
  ef_construction=64); GIN index on `content_tsv` (`simple` config, ADR-007)
- Alembic async migrations with autogenerate

### Phase 2 — Ingestion pipeline
- `crawler.py`: polite bdlaws.minlaw.gov.bd fetch with ETag/Last-Modified conditional
  requests, configurable rate limit (default 1 RPS)
- `parser.py`: selectolax HTML → `ProvisionNode` tree preserving part/chapter/section
  hierarchy
- `normalize.py`: HTML sanitisation preserving Bengali characters and numerals
- `amendments.py`: inline amendment annotation parsing; falls back to snapshot provenance
- `registry.py`: YAML-driven Act bootstrap; `get_source_urls` resolver
- `tasks.py`: Celery tasks with per-revision content-hash skip (FR-IN-4) and per-language
  isolation (FR-IN-5)

### Phase 3 — Processing (chunking + embedding)
- `chunker.py`: section-hierarchy-aware chunker with paragraph-boundary splits and
  configurable overlap; hierarchy path prepended to each chunk for retrieval context
- `embedder.py`: `CohereEmbedder` with `EmbedInputType` discriminator enforced at the
  type level (ADR-002); batched with exponential-backoff retry

### Phase 4 — Retrieval pipeline
- `lang_router.py`: Bengali Unicode-block coverage classifier (U+0980–U+09FF); returns
  `bn`, `en`, or `mixed`
- `retriever.py`: `vector_search` (HNSW cosine), `lexical_search` (websearch_to_tsquery
  `simple`), `_fuse` (Reciprocal Rank Fusion k=60); mandatory effective-date predicate
- `reranker.py`: Cohere `rerank-multilingual-v3.0`; degrades to LOW confidence on
  `RerankerUnavailable` (NFR-RL-2)
- `service.py`: full pipeline — language detection → embedding → hybrid retrieve → cross-
  lingual fallback → rerank → confidence tiering

### Phase 5 — Generation and safety
- Multi-provider LLM abstraction (`base.py`, `factory.py`): Anthropic, OpenAI, Ollama;
  runtime Redis override; content-hash response cache; cost circuit breaker
- `disclaimer.py`: versioned bilingual disclaimer; `inject()` appended on every response
  path (NFR-LS-1)
- `decline_gate.py`: bilingual regex classifier for advice-seeking queries; recall-floor
  check; runs even when retrieval returns relevant chunks (NFR-LS-3)
- `citation.py`: `{{cite:chunk_id}}` placeholder resolution; strips foreign placeholders;
  Bengali numeral rendering for BN-language responses (ADR-005)
- `guardrails.py`: versioned normative-phrase blacklist (EN + BN); one retry on violation;
  fail-open on second violation
- `generator.py`: full pipeline with cache, decline, circuit breaker, provider call,
  citation validation, guardrails, disclaimer injection; streaming (`generate_stream`)
  and batch (`generate`) modes

### Phase 6 — API and admin console
- FastAPI: `POST /api/v1/query`, `POST /api/v1/query/stream` (SSE), `POST /api/v1/feedback`
- Browse: `GET /api/v1/acts`, `GET /api/v1/acts/{slug}/structure`, `GET /api/v1/acts/{slug}/sections/{id}`
- Admin (bearer-auth): metrics, queries, acts list, per-act ingest, ingest-all, LLM
  override GET/PUT/DELETE
- React 19 + TypeScript + Tailwind v4 admin console: Dashboard, Acts Registry,
  Playground (bilingual SSE streaming), Settings
- Playwright e2e tests for all 4 pages
- 221 pytest tests passing

---

[Unreleased]: https://github.com/mralaminahamed/bd-legal-rag/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mralaminahamed/bd-legal-rag/releases/tag/v0.1.0
