# Bangladesh Legal RAG

[![CI](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml/badge.svg?branch=trunk)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml)
[![Eval](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/eval.yml/badge.svg)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/eval.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node 24](https://img.shields.io/badge/node-24-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)

**AI-powered legal research assistant grounded in Bangladeshi statute law.**

Ingests Acts from `bdlaws.minlaw.gov.bd`, stores provision revisions with effective-date windows, and answers questions via a bilingual RAG pipeline in Bengali and English. Every response carries a mandatory disclaimer and canonical section citations.

> **This is an informational research tool, not legal advice.** The system declines advice-seeking queries and never states a legal conclusion in its own voice. Every response path — including cache-hits, declines, and errors — appends the active disclaimer.

> **Status:** v1.0.0 — all phases complete · **16 Acts** indexed · 1,619+ bilingual chunks · query + stream + admin API live

---

## What is in the corpus

16 Acts indexed as of 2026-06-02. Ingestion runs against the live bdlaws portal so the snapshot date for each Act can be checked in the **Corpus Coverage** page (`/corpus`) of the admin console.

**Original 5 v1.0 Acts:**

| Act | Year |
|---|---|
| The Companies Act | 1994 |
| The Income Tax Act | 2023 |
| The Value Added Tax and Supplementary Duty Act | 2012 |
| The Bangladesh Labour Act | 2006 |
| The Digital Security Act | 2018 |

**Additional 11 Acts (added Phase 8):** Penal Code 1860, Evidence Act 1872, Contract Act 1872, Specific Relief Act 1877, Negotiable Instruments Act 1881, Transfer of Property Act 1882, Code of Criminal Procedure 1898, Code of Civil Procedure 1908, Limitation Act 1908, Partnership Act 1932, Constitution of Bangladesh 1972.

All Acts available in Bengali (authoritative) and English (reference translation). See `config/acts/` for YAML registrations and `config/bdlaws-acts-index.json` for the full 1,556-Act bdlaws index.

---

## How it works

1. **Ingestion** — Celery workers crawl bdlaws via `app/ingestion/crawler.py`, parse the statutory hierarchy with `parser.py`, and store `provisions` + `provision_revisions` keyed by effective date.
2. **Embedding** — `app/processing/embedder.py` embeds each chunk with Cohere `embed-multilingual-v3.0` (1024d, `vector`) when a Cohere key is present, or Ollama `qwen3-embedding:4b` (2560d, `halfvec`) otherwise. The `input_type` discriminator (`search_document` vs `search_query`) is enforced at the type level.
3. **Retrieval** — `app/rag/retriever.py` runs HNSW cosine vector search (pgvector) + Postgres FTS (`content_tsv`, `simple` config for Bengali) and merges via Reciprocal Rank Fusion. Cohere `rerank-multilingual-v3.0` is the mandatory final stage — degrades to `LOW` confidence when unreachable.
4. **Generation** — `app/rag/generator.py` runs the fixed pipeline: cache → decline gate → cost circuit breaker → LLM (Claude / OpenAI / Ollama) → citation validator → guardrails → disclaimer injection.
5. **Safety** — The `decline_gate` detects advice-seeking patterns in Bengali and English. The `guardrails` scanner blocks normative conclusions in the system's voice. `disclaimer.inject()` runs on every code path.

---

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.12 · FastAPI 0.115 · SQLAlchemy 2.0 async · Alembic · Pydantic v2 |
| Workers | Celery 5 · Redis · httpx async |
| Database | PostgreSQL 16 · pgvector 0.8.2 · HNSW cosine · `halfvec(2560)` or `vector(1024)` |
| Embeddings | Cohere `embed-multilingual-v3.0` (1024d) · Ollama `qwen3-embedding:4b` (2560d, local fallback) |
| LLM | Claude `claude-sonnet-4-6` · OpenAI `gpt-4o-mini` · Ollama `gemma4:e2b` |
| Reranker | Cohere `rerank-multilingual-v3.0` |
| Frontend | React 19 · TypeScript 6 · Vite 8 · Tailwind CSS v4 · TanStack Query 5 |
| Infra | Docker Compose · GitHub Actions CI/Eval/Deploy · Caddy (prod TLS) |

---

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ with [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Node.js 24+ with [pnpm](https://pnpm.io/) (`npm i -g pnpm`)

**For local-only dev (no cloud keys needed):**
- [Ollama](https://ollama.com) running on the host with `gemma4:e2b` and `qwen3-embedding:4b` pulled

**For production quality retrieval:**
- `BDRAG_COHERE_API_KEY` — embeddings + mandatory reranking

**Optional cloud LLM providers:**
- `BDRAG_ANTHROPIC_API_KEY` — Claude
- `BDRAG_OPENAI_API_KEY` — OpenAI

---

## Quick start (Ollama, no cloud keys)

```bash
# 1. Clone
git clone https://github.com/mralaminahamed/bd-legal-rag.git
cd bd-legal-rag

# 2. Create .env (gitignored)
cat > .env << 'EOF'
BDRAG_DEFAULT_PROVIDER=ollama
BDRAG_OLLAMA_MODEL=gemma4:e2b
BDRAG_OLLAMA_EMBED_MODEL=qwen3-embedding:4b
BDRAG_ADMIN_BEARER_TOKEN=$(openssl rand -hex 32)
BDRAG_DECLINE_RECALL_FLOOR=0.001
VITE_API_BASE_URL=http://localhost:8000
VITE_ADMIN_TOKEN=dev-admin-token
EOF

# 3. Pull Ollama models (host, not container)
ollama pull gemma4:e2b
ollama pull qwen3-embedding:4b

# 4. Start the stack
docker compose up -d

# 5. Run migrations + seed sample data
docker compose exec app alembic upgrade head
cd apps/api && uv run python -m app.seeders --fresh

# 6. Bootstrap + ingest all 16 Acts (crawls bdlaws.minlaw.gov.bd; ~20 min)
docker compose exec app python -m app.ingestion.registry bootstrap
curl -X POST http://localhost:8000/api/v1/admin/acts/ingest \
  -H "Authorization: Bearer dev-admin-token"

# 7. Watch ingestion
docker compose logs -f worker | grep -E "succeeded|failed|chunks_created"

# 8. Open the operator console
open http://localhost:8080
```

**Services:**

| Service | URL | Notes |
|---|---|---|
| API | http://localhost:8000 | Swagger UI at `/docs` |
| Admin console | http://localhost:8080 | Dashboard, Acts, Corpus Coverage, Playground, Settings |
| PostgreSQL | `localhost:5432` | pgvector database (db: `bdrag`, user: `bdrag`) |
| Redis | `localhost:6379` | Celery broker + response cache |

**Key environment variables:**

```bash
# Generation
BDRAG_DEFAULT_PROVIDER=ollama          # anthropic | openai | ollama
BDRAG_OLLAMA_MODEL=gemma4:e2b
BDRAG_OLLAMA_EMBED_MODEL=qwen3-embedding:4b

# Production embeddings + reranking
BDRAG_COHERE_API_KEY=co-...

# Admin API (required)
BDRAG_ADMIN_BEARER_TOKEN=...           # generate: openssl rand -hex 32

# Decline gate (calibrated for RRF score range ~0.025 max)
BDRAG_DECLINE_RECALL_FLOOR=0.001
```

---

## Admin console pages

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Service health, 24h metrics, recent queries |
| Acts Registry | `/acts` | 16 registered Acts; trigger ingestion per-Act or all |
| Corpus Coverage | `/corpus` | BN/EN coverage, chunk counts, snapshot dates, temporal limits |
| Playground | `/playground/:threadId` | Bilingual chat — each conversation gets a UUID sub-route |
| Settings | `/settings` | LLM provider override, health probes |

---

## API reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Liveness + DB/Redis status |
| `POST` | `/api/v1/query` | rate-limited | Grounded answer with citations + disclaimer |
| `POST` | `/api/v1/query/stream` | rate-limited | SSE: `token` events then `final` with citation-validated content |
| `POST` | `/api/v1/feedback` | rate-limited | Bind `helpful`/`not_helpful`/`wrong_citation`/`out_of_scope` to a `query_id` |
| `GET` | `/api/v1/acts` | — | List registered Acts |
| `GET` | `/api/v1/acts/{slug}/structure` | — | Statutory tree: Part → Chapter → Section |
| `GET` | `/api/v1/acts/{slug}/sections/{id}` | — | Provision text + hierarchy path + disclaimer |
| `POST` | `/api/v1/admin/acts/ingest` | bearer | Trigger ingestion for all Acts (1 task per act × language) |
| `POST` | `/api/v1/admin/acts/{slug}/ingest` | bearer | Trigger ingestion for one Act |
| `GET` | `/api/v1/admin/acts` | bearer | Acts with ingestion state per language |
| `GET` | `/api/v1/admin/metrics` | bearer | 24h metrics: decline rate, cache hit rate, p95 latency, daily spend |
| `GET` | `/api/v1/admin/queries` | bearer | Recent queries (`?limit=N`) |
| `GET·PUT·DELETE` | `/api/v1/admin/llm` | bearer | Read / override / clear the active provider+model |

Full interactive docs: `http://localhost:8000/docs`

---

## Corpus management

```bash
# Register Acts from config/acts/*.yaml
cd apps/api && uv run python -m app.ingestion.registry bootstrap

# Seed sample data (fake embeddings — good for dashboard testing)
cd apps/api && uv run python -m app.seeders --fresh

# Trigger full ingestion via API
curl -X POST http://localhost:8000/api/v1/admin/acts/ingest \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# Single Act
curl -X POST http://localhost:8000/api/v1/admin/acts/labour-act-2006/ingest \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# Monitor
docker compose logs -f worker | grep -E "succeeded|failed|chunks_created"
```

**Adding a new Act:** create `config/acts/<slug>.yaml`, rebuild the API image so the YAML is copied in, run `bootstrap`, trigger ingestion, add ≥ 4 BN + 4 EN records to `apps/api/eval/dataset/golden.jsonl`, and run `python -m eval.harness`. See [RUNBOOK.md](RUNBOOK.md#8-add-a-new-act) for the full procedure.

---

## Database migrations

```bash
# Apply all pending (inside container)
docker compose exec app alembic upgrade head

# Apply all pending (local dev, from apps/api/)
uv run alembic upgrade head

# Create autogenerated migration
uv run alembic revision --autogenerate -m "describe change"

# Rollback one step
uv run alembic downgrade -1
```

Current schema: 7 tables (`acts`, `provisions`, `provision_revisions`, `chunks`, `ingestion_runs`, `queries`, `feedback`). The `chunks.embedding` column is `halfvec(2560)` with an HNSW index using `halfvec_cosine_ops`.

---

## Development

```bash
# Backend (from apps/api/)
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict app eval
uv run pytest -q                          # 221 tests; all external calls mocked/VCR-replayed
uv run python -m eval.harness             # offline eval gate

# Frontend (from apps/web/)
pnpm install
pnpm dev                                  # → http://localhost:5174
pnpm type-check
pnpm build
pnpm e2e                                  # Playwright (API mocked)
```

**Quality gates (must pass before merge):**

```
ruff check + format --check
mypy --strict app eval
pytest
pnpm type-check && pnpm build

# On changes to app/prompts/, app/rag/, eval/dataset/:
python -m eval.harness
# Thresholds: section_citation_accuracy ≥ 0.85
#             language_routing_accuracy ≥ 0.95
#             decline_accuracy          ≥ 0.95
```

---

## Production deployment

```bash
export DOMAIN=legal.example.com
export POSTGRES_PASSWORD=$(openssl rand -hex 32)
export BDRAG_ADMIN_BEARER_TOKEN=$(openssl rand -hex 32)
export BDRAG_COHERE_API_KEY=co-...
export BDRAG_ANTHROPIC_API_KEY=sk-ant-...

docker compose -f docker-compose.prod.yml up -d
```

Caddy provisions and renews TLS automatically for `$DOMAIN`. The admin console is served at `https://$DOMAIN`. All secrets are environment-only — none are baked into images.

See [RUNBOOK.md](RUNBOOK.md) for day-two operations: bootstrap, ingestion, prompt rollback, disclaimer updates, LLM override, and incident response.

---

## Project structure

```
bd-legal-rag/
├── apps/
│   ├── api/                    # Python backend
│   │   ├── app/
│   │   │   ├── api/            # FastAPI routes + schemas + deps
│   │   │   ├── db/             # Engine, SQLAlchemy models, Alembic migrations
│   │   │   ├── ingestion/      # bdlaws crawler, parser, amendments, Celery tasks
│   │   │   ├── llm/            # Provider protocol (Claude/OpenAI/Ollama), factory, runtime
│   │   │   ├── processing/     # Section-hierarchy chunker, embedder (Cohere + Ollama)
│   │   │   ├── prompts/        # Versioned prompts + safety (disclaimer, decline)
│   │   │   ├── rag/            # lang_router, retriever, reranker, service, decline_gate,
│   │   │   │                   #   confidence, citation, guardrails, generator
│   │   │   ├── seeders/        # Laravel-style seeders (acts, corpus, queries, feedback)
│   │   │   └── config.py       # pydantic-settings; single source of all tunables
│   │   ├── eval/
│   │   │   ├── dataset/golden.jsonl   # 84-record bilingual golden dataset
│   │   │   ├── metrics.py             # 5 legal-domain metrics
│   │   │   └── harness.py             # Offline eval harness (python -m eval.harness)
│   │   └── tests/              # pytest; all external calls mocked or VCR-replayed
│   └── web/                    # React 19 + Vite 8 admin console
│       └── src/
│           ├── pages/          # Dashboard, ActsPage, CorpusPage, PlaygroundPage, SettingsPage
│           ├── components/     # Layout + reusable UI (CVA, Tailwind v4)
│           ├── api/            # Axios clients (public + admin)
│           └── types/          # Shared TypeScript interfaces
├── caddy/Caddyfile             # Reverse proxy + TLS config
├── config/
│   ├── acts/                   # 16 Act YAML registrations
│   └── bdlaws-acts-index.json  # Full index of 1,556 Acts from bdlaws portal
├── docs/
│   ├── 01-SRS.md               # Software Requirements Specification
│   └── 02-Architecture.md      # Architecture + ADRs
├── .github/
│   ├── workflows/              # ci.yml · eval.yml · deploy.yml
│   ├── ISSUE_TEMPLATE/         # bug_report.yml · feature_request.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── CHANGELOG.md
├── CONTRIBUTING.md
├── RUNBOOK.md                  # Day-two operations
├── SECURITY.md
├── docker-compose.yml          # Dev stack (Ollama local)
└── docker-compose.prod.yml     # Prod stack (Caddy auto-TLS)
```

---

## What is genuinely different

If you have built a general-purpose RAG before, four things change in a legal domain:

1. **The disclaimer is application output, not model output** — `generator.py` appends it to every user-visible response including cache-hits, declines, fail-open, and errors. The LLM never sees the disclaimer text. Changing it requires an eval harness pass (eval-gated, versioned in `app/prompts/safety/disclaimer.py`).

2. **Citations are placeholders resolved post hoc** — the LLM emits `{{cite:chunk_id}}`; `app/rag/citation.py` renders canonical English or Bengali strings (with Bengali numeral conversion). Any placeholder whose `chunk_id` is not in the supplied set is stripped. Citation accuracy is testable offline without running a model.

3. **Rerank is mandatory, not optional** — legal precision demands a cross-encoder pass. The system degrades to `LOW` confidence rather than failing when the reranker is unreachable (`RerankerUnavailable`). Vector-only retrieval is never served without the rerank pass completing or explicitly degrading.

4. **The data model is temporal** — `provision_revisions` records effective windows (`effective_from`, `effective_to`). Every retrieval query includes a mandatory `as_of_date` predicate. A query about the 2010 form of a provision must not be served the 2024 amendment.

---

## Corpus source

All statutory text is sourced from the official Bangladesh law portal maintained by the Ministry of Law, Justice and Parliamentary Affairs:

```
https://bdlaws.minlaw.gov.bd/laws-of-bangladesh-alphabetical-index.html
```

Act pages follow the pattern `http://bdlaws.minlaw.gov.bd/act-{id}.html` (Bengali) and `http://bdlaws.minlaw.gov.bd/act-{id}.html?lang=en` (English reference translation). The page IDs for each registered Act are in the corresponding `config/acts/<slug>.yaml` file.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — includes non-negotiable safety rules, where-things-go table, and the eval gate requirement for all RAG/prompt changes.

## Security

See [SECURITY.md](SECURITY.md) — includes the responsible disclosure contact and a table of the security design decisions built into the pipeline.

## License

MIT © 2026 [Al Amin Ahamed](https://github.com/mralaminahamed)
