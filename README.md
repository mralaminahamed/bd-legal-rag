# Bangladesh Legal RAG

[![CI](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml/badge.svg?branch=trunk)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml)
[![Security Audit](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/security.yml/badge.svg)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/security.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node 24](https://img.shields.io/badge/node-24-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)

**AI-powered legal research assistant grounded in Bangladeshi statute law.**

Ingests the full text of Acts from `bdlaws.minlaw.gov.bd`, stores provision revisions with effective-date windows, and answers questions via a bilingual RAG pipeline in Bengali and English — every response carrying a mandatory disclaimer and canonical citations.

> **This is an informational research tool, not legal advice.** Every response carries a mandatory bilingual disclaimer. The system declines advice-seeking queries and never states a legal conclusion in its own voice.

> **Status:** v1.0.0 — Phase 4 complete · 5 Acts indexed · query + stream + admin API live

---

## Features

### Legal Corpus
- **5 v1.0 Acts** — Companies Act 1994, Income Tax Act 2023, VAT and SD Act 2012, Labour Act 2006, Digital Security Act 2018; both Bengali and English
- **Temporal corpus** — `provision_revisions` track effective windows; retrieval filters by `as_of_date` (default today); ask about the 2010 form of a provision, get the 2010 text
- **1 556 Acts indexed** — full bdlaws index at `config/bdlaws-acts-index.json`; declarative YAML registration in `config/acts/`
- **Hierarchy-aware chunking** — section-level chunks preserve Part → Chapter → Section → Subsection → Clause path
- **Bilingual embeddings** — Cohere `embed-multilingual-v3.0` at 1024 dims; `input_type` asymmetry enforced at the type level (search_document at ingest, search_query at retrieval)

### RAG Pipeline
- **Hybrid retrieval** — HNSW cosine (pgvector) + Postgres FTS (`content_tsv`, `simple` config for Bengali) merged by Reciprocal Rank Fusion
- **Mandatory rerank** — Cohere `rerank-multilingual-v3.0`; degrades to `LOW` confidence when unreachable; never fails the request
- **Language routing** — Bengali Unicode-block analysis; query and response language matched
- **Decline gate** — detects "should I…", "what should I do if…", "is it legal for me to…" and Bengali equivalents; declines even when retrieval would return relevant chunks
- **Citation validation** — LLM emits `{{cite:chunk_id}}` placeholders; resolved post hoc into canonical bilingual strings with Bengali numeral conversion; supplied-chunk-only enforcement
- **Guardrails** — versioned bilingual blacklist blocks normative conclusions in the system's own voice; one retry then fail-open
- **Mandatory disclaimer** — application-controlled, appended to every response by `generator.py`; never in the prompt; cache-hits re-assert active version

### Platform
- **Multi-provider generation** — Claude, OpenAI, or Ollama; interchangeable by config; switchable at runtime from the operator console
- **Streaming** — SSE `/api/v1/query/stream`; provisional `token` events then `final` with citation-validated content
- **Content-hash response cache** — key includes query, ordered chunk IDs, `as_of_date`, model, prompt version, reranker version
- **Fail-open** — provider unreachable → return retrieved provisions + citations + disclaimer with `degraded=true`
- **Cost circuit breaker** — refuses calls projected to exceed per-request ceiling
- **Feedback loop** — bind `helpful` / `not_helpful` / `wrong_citation` / `out_of_scope` to a `query_id`

### Operator Console (`apps/web`, `:8080`)
- **Dashboard** — service health, query metrics, corpus coverage, recent activity feed
- **Acts** — searchable/sortable registry; expand an Act to see its sources and trigger ingestion
- **Playground** — bilingual chat-style interface for grounded, cited Q&A (streamed)
- **Settings** — switch the generation provider/model at runtime, test the API connection

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.12 · FastAPI 0.115 · SQLAlchemy 2.0 async · Alembic · Pydantic v2 |
| Workers | Celery 5 · Redis · httpx async |
| Database | PostgreSQL 16 · pgvector (HNSW cosine, 1024d) |
| LLM | Cohere `embed-multilingual-v3.0` + `rerank-multilingual-v3.0` · Claude `claude-sonnet-4-6` · OpenAI `gpt-4o-mini` · Ollama |
| Frontend | React 19 · TypeScript 6 · Vite 8 · Tailwind CSS v4 · TanStack Query 5 |
| Infra | Docker Compose · GitHub Actions · Caddy (prod) |

---

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 24+ and [pnpm](https://pnpm.io/)
- API key: `BDRAG_COHERE_API_KEY` (embeddings + reranking — the only required external API)

Optional (for generation beyond Ollama):
- `BDRAG_ANTHROPIC_API_KEY` — Claude provider
- `BDRAG_OPENAI_API_KEY` — OpenAI provider

---

## Quick Start

```bash
# 1. Clone + configure
git clone https://github.com/mralaminahamed/bd-legal-rag.git
cd bd-legal-rag
cp .env.example .env
# Edit .env — at minimum set BDRAG_COHERE_API_KEY and BDRAG_ADMIN_BEARER_TOKEN

# 2. Start the full stack (builds all images)
docker compose up -d --build

# 3. Run migrations
docker compose exec app uv run alembic upgrade head

# 4. Seed the five v1.0 Acts
docker compose exec app uv run python -m app.ingestion.registry bootstrap

# 5. Trigger ingestion
curl -X POST http://localhost:8000/api/v1/admin/ingest \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# 6. Watch the workers
docker compose logs -f worker

# 7. Open the operator console
open http://localhost:8080
```

> Minimum requirements: Docker 24+, 4 GB RAM, ports 8000 and 8080 free.

**Services after `docker compose up`:**

| Service | URL | Description |
|---|---|---|
| API | http://localhost:8000 | FastAPI + Swagger at `/docs` |
| Operator console | http://localhost:8080 | React admin dashboard |
| PostgreSQL | `localhost:5432` | pgvector database |
| Redis | `localhost:6379` | Celery broker + cache |

**Environment variables (`.env`):**

```bash
BDRAG_COHERE_API_KEY=...          # embeddings + reranking (required)
BDRAG_ANTHROPIC_API_KEY=...       # Claude provider (optional)
BDRAG_OPENAI_API_KEY=...          # OpenAI provider (optional)
BDRAG_DEFAULT_PROVIDER=ollama     # generation: anthropic | openai | ollama
BDRAG_OLLAMA_BASE_URL=http://host.docker.internal:11434
BDRAG_ADMIN_BEARER_TOKEN=...      # admin endpoints (required)
```

Generate the admin token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│          Browser (React 19 + Vite 8 + Tailwind v4)               │
│          TanStack Query · React Router · shadcn/ui               │
│               Operator Console  :8080                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼───────────────────────────────────────┐
│                    FastAPI (Python 3.12)                          │
│  /api/v1/query  /api/v1/query/stream  /api/v1/feedback           │
│  /api/v1/acts   /api/v1/admin/*                                  │
│  ├─ language router  (Bengali Unicode-block analysis)            │
│  ├─ decline gate     (advice-seeking detection, bilingual)       │
│  ├─ hybrid retriever (HNSW cosine + Postgres FTS → RRF)          │
│  ├─ mandatory reranker  (Cohere rerank-multilingual-v3.0)        │
│  ├─ generator    (cache → cost breaker → provider → guardrails)  │
│  ├─ citation validator  ({{cite:id}} → canonical strings)        │
│  └─ disclaimer injector (application-controlled, every path)     │
│                     :8000                                         │
└──────┬───────────────────────┬──────────────────┬───────────────┘
       │                       │                  │
┌──────▼──────────┐  ┌─────────▼──────┐  ┌────────▼───────┐
│  PostgreSQL 16  │  │     Redis       │  │ Celery workers  │
│  + pgvector     │  │  broker+cache   │  │  ingest · embed │
│  (HNSW 1024d)  │  │                 │  │  amendments     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Project Structure

```
bd-legal-rag/
├── apps/
│   ├── api/                        # Python backend
│   │   ├── app/
│   │   │   ├── api/                # FastAPI routes (query, browse, admin) + schemas + deps
│   │   │   ├── db/                 # Async engine, SQLAlchemy 2.0 models, Alembic migrations
│   │   │   ├── ingestion/          # bdlaws crawler, parser, amendments, Celery tasks
│   │   │   ├── llm/                # Provider protocol + impls (Claude/OpenAI/Ollama), factory, runtime
│   │   │   ├── processing/         # Section-hierarchy chunker, Cohere multilingual embedder
│   │   │   ├── prompts/            # Versioned prompts + safety (disclaimer, decline)
│   │   │   ├── rag/                # lang_router, retriever, reranker, service, decline_gate,
│   │   │   │                       #   confidence, citation, guardrails, generator
│   │   │   └── config.py           # pydantic-settings; single source of all tunables
│   │   ├── eval/                   # Bilingual golden dataset, harness, metrics
│   │   ├── tests/                  # pytest + asyncio; all external calls mocked/VCR-replayed
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   └── web/                        # React 19 + Vite 8 operator console
│       └── src/
│           ├── api/                # Axios API clients
│           ├── components/         # ui/ + domain components
│           ├── features/           # Acts, Playground, Dashboard, Settings
│           ├── pages/              # One file per route
│           └── types/              # Shared TypeScript interfaces
├── config/
│   ├── acts/                       # Declarative Act registrations (5 v1.0 Acts)
│   └── bdlaws-acts-index.json      # Full index of 1 556 Acts
├── docs/                           # SRS, Architecture, Implementation Plan, ADRs, Prompts
├── .env.example
├── docker-compose.yml              # Dev stack
└── docker-compose.prod.yml         # Prod stack (Caddy TLS)
```

---

## API Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Liveness + DB/Redis probes |
| `POST` | `/api/v1/query` | rate limit | Ask a question; returns cited answer + disclaimer |
| `POST` | `/api/v1/query/stream` | rate limit | Same, streamed as SSE: `token` events then `final` |
| `POST` | `/api/v1/feedback` | rate limit | Bind helpful/not_helpful/wrong_citation/out_of_scope to a query_id |
| `GET` | `/api/v1/acts` | — | List Acts with status, ministry, snapshot date |
| `GET` | `/api/v1/acts/{slug}/structure` | — | Statutory tree: Part → Chapter → Section |
| `GET` | `/api/v1/acts/{slug}/sections/{section}` | — | Provision text + hierarchy path + disclaimer |
| `POST` | `api/v1/admin/ingest` | bearer | Trigger ingestion for all Acts |
| `POST` | `/api/v1/admin/ingest/{slug}` | bearer | Trigger ingestion for one Act (one task per language) |
| `GET` | `/api/v1/admin/acts` | bearer | List Acts with source counts and ingestion state |
| `GET` | `/api/v1/admin/metrics` | bearer | Decline rate, mean confidence, citation accuracy, p95 latency, cache-hit rate, daily spend |
| `GET` | `/api/v1/admin/queries` | bearer | Recent queries for the activity feed (`?limit=`) |
| `GET·PUT·DELETE` | `/api/v1/admin/llm` | bearer | Read / override / reset the active generation provider+model |

Full interactive docs at `http://localhost:8000/docs` (Swagger UI) after starting the stack.

---

## Corpus Management

```bash
# Seed the five v1.0 Acts from config/acts/*.yaml
docker compose exec app uv run python -m app.ingestion.registry bootstrap

# Trigger ingestion for all Acts (one Celery task per act × language)
curl -X POST http://localhost:8000/api/v1/admin/ingest \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# Trigger ingestion for a single Act
curl -X POST http://localhost:8000/api/v1/admin/ingest/labour-act-2006 \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# Watch ingestion progress
docker compose logs -f worker

# Bootstrap new Acts from CLI (local dev)
cd apps/api
uv run python -m app.ingestion.registry bootstrap
```

Adding a new Act: create `config/acts/<slug>.yaml`, run bootstrap, trigger ingestion, add ≥ 8 records to `eval/dataset/golden.jsonl`, and run the eval harness.

---

## Database Migrations

```bash
# Apply all pending (inside container)
docker compose exec app uv run alembic upgrade head

# Apply all pending (local dev)
cd apps/api && uv run alembic upgrade head

# Create autogenerated migration
cd apps/api && uv run alembic revision --autogenerate -m "describe change"

# Rollback one step
cd apps/api && uv run alembic downgrade -1
```

---

## Development

```bash
# Backend (from apps/api/)
uv sync                                       # install all deps including dev
uv run ruff check . && uv run ruff format --check .   # lint + format
uv run mypy --strict app eval                 # type check
uv run pytest -x --cov=app                   # tests (all external calls mocked/VCR-replayed)
uv run python -m eval.harness                # offline eval gate

# Frontend (from apps/web/)
pnpm install
pnpm dev                                      # Vite dev server → http://localhost:5174
pnpm type-check
pnpm lint
pnpm build
pnpm e2e                                      # Playwright (API mocked)
```

**CI quality gates** (must pass before merge):

```bash
# Backend
ruff check . && ruff format --check .
mypy --strict app eval
pytest

# Frontend
pnpm type-check
pnpm lint
pnpm build

# Eval (runs on prompt/RAG/dataset changes)
python -m eval.harness
# Thresholds: citation accuracy ≥ 0.85 · language routing ≥ 0.95 · decline accuracy ≥ 0.95
```

---

## Production Deployment

```bash
DOMAIN=legal.example.com \
POSTGRES_PASSWORD=... \
BDRAG_ADMIN_BEARER_TOKEN=... \
BDRAG_COHERE_API_KEY=... \
BDRAG_ANTHROPIC_API_KEY=... \
docker compose -f docker-compose.prod.yml up -d
```

Caddy terminates TLS automatically for `$DOMAIN`. The operator console is served at `$DOMAIN:8080`. All secrets are environment-only. See `RUNBOOK.md` for day-two operations.

---

## What Is Genuinely Different About This Project

If you have built a general-purpose RAG before, four things change here:

1. **The disclaimer is application output, not model output** (ADR-004). Every user-visible response — cache-hits, declines, fail-open, errors — is wrapped by `apps/api/app/rag/generator.py`'s injector. The LLM never sees the disclaimer.
2. **Citations are placeholders resolved post hoc** (ADR-005). The LLM emits `{{cite:chunk_id}}`; `apps/api/app/rag/citation.py` renders canonical English or Bengali strings with Bengali numeral conversion. Citation accuracy is testable without model quality.
3. **Rerank is mandatory** (ADR-003). Legal precision demands a cross-encoder pass. When the reranker is unreachable, the system degrades to `LOW` confidence rather than failing.
4. **The data model is temporal** (ADR-006). `provision_revisions` track effective windows, and retrieval always filters by `as_of_date`. A question about the 2010 form of a provision must not be served the 2024 amendment.

---

## Corpus Source

All Acts are sourced from the Bangladesh national law portal:

- **Index page:** http://bdlaws.minlaw.gov.bd/laws-of-bangladesh-alphabetical-index.html
- **Act page pattern:** `http://bdlaws.minlaw.gov.bd/act-{id}.html` (Bengali default)
- **English variant:** `http://bdlaws.minlaw.gov.bd/act-{id}.html?lang=en`

The five v1.0 Acts and their confirmed page IDs:

| Act | bdlaws ID | URL |
|---|---|---|
| The Companies Act, 1994 | 788 | http://bdlaws.minlaw.gov.bd/act-788.html |
| The Income Tax Act, 2023 | 1429 | http://bdlaws.minlaw.gov.bd/act-1429.html |
| The VAT and Supplementary Duty Act, 2012 | 1106 | http://bdlaws.minlaw.gov.bd/act-1106.html |
| The Bangladesh Labour Act, 2006 | 952 | http://bdlaws.minlaw.gov.bd/act-952.html |
| The Digital Security Act, 2018 | 1261 | http://bdlaws.minlaw.gov.bd/act-1261.html |

---

## Contributing

See [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## Security

See [`.github/SECURITY.md`](.github/SECURITY.md).

## License

MIT © 2026 [Al Amin Ahamed](https://alaminahamed.com)
