# Bangladesh Legal RAG

[![CI](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml/badge.svg?branch=trunk)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml)
[![Eval](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/eval.yml/badge.svg)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/eval.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node 24](https://img.shields.io/badge/node-24-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)

**AI-powered legal research assistant grounded in Bangladeshi statute law.**

Ingests Acts from `bdlaws.minlaw.gov.bd`, stores provision revisions with effective-date windows, and answers questions via a bilingual RAG pipeline in Bengali and English. Supports five query modes: legal Q&A, legal advice, act summary, section listing, and act explanation. Every response carries a mandatory disclaimer and canonical section citations linked to the bdlaws source page.

> **Status:** v1.0 · 16 Acts indexed · bilingual (BN authoritative + EN reference) · query + stream + admin API live

---

## What is in the corpus

16 Acts indexed, available in Bengali (authoritative) and English (reference translation).

| Act | Year | bdlaws ID |
|---|---|---|
| The Penal Code | 1860 | act-11 |
| The Evidence Act | 1872 | act-24 |
| The Contract Act | 1872 | act-26 |
| The Specific Relief Act | 1877 | act-36 |
| The Negotiable Instruments Act | 1881 | act-46 |
| The Transfer of Property Act | 1882 | act-48 |
| The Code of Criminal Procedure | 1898 | act-75 |
| The Code of Civil Procedure | 1908 | act-86 |
| The Limitation Act | 1908 | act-88 |
| The Partnership Act | 1932 | act-157 |
| The Constitution of Bangladesh | 1972 | act-367 |
| The Bangladesh Labour Act | 2006 | act-952 |
| The Value Added Tax and Supplementary Duty Act | 2012 | act-1106 |
| The Digital Security Act | 2018 | act-1261 |
| The Companies Act | 1994 | act-788 |
| The Income Tax Act | 2023 | act-1429 |

YAML registrations: `config/acts/`. Full 1,556-Act bdlaws index: `config/bdlaws-acts-index.json`.

---

## How it works

1. **Snapshot** — `app/ingestion/snapshot.py` crawls `bdlaws.minlaw.gov.bd` and saves raw HTML to `data/raw/{slug}/{lang}.html`. Subsequent ingestions read from disk — no network calls until you `--force`.
2. **Ingestion** — Celery workers parse the statutory hierarchy, store `provisions` + `provision_revisions` keyed by effective date. Content-hash comparison skips re-embedding unchanged text.
3. **Embedding** — `app/processing/embedder.py` uses Cohere `embed-multilingual-v3.0` (1024d) when a key is present, or Ollama `qwen3-embedding:4b` (2560d, `halfvec`) otherwise. The `input_type` discriminator (`search_document` vs `search_query`) is enforced at the type level.
4. **Retrieval** — HNSW cosine vector search (pgvector) + Postgres FTS (`simple` config for Bengali) merged via Reciprocal Rank Fusion. Cohere `rerank-multilingual-v3.0` is the mandatory final stage.
5. **Intent routing** — `app/rag/intent.py` classifies every query into one of five intents and routes to the correct prompt and handler.
6. **Generation** — `app/rag/generator.py`: cache → intent route → decline gate → cost circuit breaker → LLM → postprocessor → citation resolver → guardrails → disclaimer injection.

---

## Query modes

| Query type | Example | Handler |
|---|---|---|
| **Legal Q&A** | "What is the penalty for digital fraud?" | Citation-based answer from retrieved provisions |
| **Legal advice** | "Can I sue my employer for unpaid wages?" | Practical guidance framed as "Under Section X…" |
| **Act summary** | "Summarize the Labour Act" | Prose summary synthesised from top provisions |
| **Section list** | "List sections of the Companies Act" | DB query — no LLM, instant |
| **Act explain** | "What does the VAT Act cover?" | Overview of scope, applicability, key provisions |

---

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.12 · FastAPI 0.115 · SQLAlchemy 2.0 async · Alembic · Pydantic v2 |
| Workers | Celery 5 · Redis · httpx async |
| Database | PostgreSQL 16 · pgvector 0.8.2 · HNSW cosine · `halfvec(2560)` or `vector(1024)` |
| Embeddings | Cohere `embed-multilingual-v3.0` (1024d) · Ollama `qwen3-embedding:4b` (2560d, local fallback) |
| LLM | Claude `claude-sonnet-4-6` · OpenAI `gpt-4o-mini` · Ollama `gemma4:e2b` (default) |
| Reranker | Cohere `rerank-multilingual-v3.0` |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 · TanStack Query 5 |
| Infra | Docker Compose · GitHub Actions CI/Eval/Deploy · Caddy (prod TLS) |

---

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ with [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Node.js 24+ with [pnpm](https://pnpm.io/) (`npm i -g pnpm`)

**Local dev (no cloud keys needed):**
- [Ollama](https://ollama.com) running on the host with `gemma4:e2b` and `qwen3-embedding:4b` pulled

**For production quality retrieval:**
- `BDRAG_COHERE_API_KEY` — embeddings + mandatory reranking

**Optional cloud LLM:**
- `BDRAG_ANTHROPIC_API_KEY` — Claude · `BDRAG_OPENAI_API_KEY` — OpenAI

---

## Quick start (Ollama, no cloud keys)

```bash
# 1. Clone
git clone https://github.com/mralaminahamed/bd-legal-rag.git
cd bd-legal-rag

# 2. Create .env at repo root (gitignored)
cat > .env << 'EOF'
BDRAG_DEFAULT_PROVIDER=ollama
BDRAG_OLLAMA_MODEL=gemma4:e2b
BDRAG_OLLAMA_EMBED_MODEL=qwen3-embedding:4b
BDRAG_ADMIN_BEARER_TOKEN=dev-admin-token
BDRAG_DECLINE_RECALL_FLOOR=0.001
VITE_API_BASE_URL=http://localhost:8000
VITE_ADMIN_TOKEN=dev-admin-token
EOF

# 3. Pull Ollama models (on host, not in container)
ollama pull gemma4:e2b
ollama pull qwen3-embedding:4b

# 4. Start the stack
docker compose up -d

# 5. Run migrations
docker compose exec app alembic upgrade head

# 6. Seed sample data (optional — populates dashboard with fake data)
cd apps/api && uv run python -m app.seeders --fresh

# 7. Bootstrap Act registrations from config/acts/*.yaml
docker compose exec app python -m app.ingestion.registry bootstrap

# 8. Snapshot all 16 Acts from bdlaws (saves to data/raw/ — ~2 min)
cd apps/api && uv run python -m app.ingestion.snapshot

# 9. Ingest all Acts from snapshots (parse + embed — ~30-60 min for all 16)
cd apps/api && uv run python -m app.ingestion.registry ingest-all

# 10. Watch ingestion progress
docker compose logs -f worker | grep -E "succeeded|failed|chunks"

# 11. Open the console
open http://localhost:8080
```

**Services:**

| Service | URL |
|---|---|
| Admin console | http://localhost:8080 |
| API + Swagger | http://localhost:8000 · http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` (db: `bdrag`, user: `bdrag`) |
| Redis | `localhost:6379` |

**Key environment variables:**

```bash
BDRAG_DEFAULT_PROVIDER=ollama          # anthropic | openai | ollama
BDRAG_OLLAMA_MODEL=gemma4:e2b
BDRAG_OLLAMA_EMBED_MODEL=qwen3-embedding:4b
BDRAG_COHERE_API_KEY=co-...            # enables Cohere embeddings + reranking
BDRAG_ADMIN_BEARER_TOKEN=...           # generate: openssl rand -hex 32
BDRAG_DECLINE_RECALL_FLOOR=0.001       # calibrated for RRF score range ~0.025 max
BDRAG_ACTIVE_PROMPT_VERSION=v2         # v1 | v2 (v2 = structured anti-slop)
BDRAG_DECLINE_GATE_ENABLED=true        # set false to allow all query types
```

---

## Console pages

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Service health, 24h metrics, recent queries |
| Acts Registry | `/acts` | 16 Acts with ingestion state, chunk counts, snapshot dates; trigger per-Act or all |
| Playground | `/playground/:threadId` | Bilingual chat — UUID thread per conversation, language toggle in topbar |
| Conversations | `/threads` | All threads with message count and last activity |
| Act Reader | `/acts/:slug/read/:sectionId` | Section-by-section ebook reader with TOC, prev/next, bdlaws source links |

---

## API reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Liveness + DB/Redis status |
| `POST` | `/api/v1/query` | rate-limited | Grounded answer with citations + disclaimer |
| `POST` | `/api/v1/query/stream` | rate-limited | SSE: `token` events then `final` event |
| `POST` | `/api/v1/feedback` | rate-limited | Bind `helpful`/`not_helpful`/`out_of_scope` to a `query_id` |
| `GET` | `/api/v1/acts` | — | List all registered Acts |
| `GET` | `/api/v1/acts/{slug}/structure` | — | Provision tree: Part → Chapter → Section (Redis-cached 1h) |
| `GET` | `/api/v1/acts/{slug}/sections/{section}` | — | Provision by number |
| `GET` | `/api/v1/provisions/{uuid}` | — | Provision by UUID (Redis-cached 6h) |
| `GET` | `/api/v1/thread/{thread_id}` | — | Messages for a conversation thread |
| `GET` | `/api/v1/threads` | — | List all threads |
| `POST` | `/api/v1/admin/acts/ingest` | bearer | Trigger ingestion for all Acts |
| `DELETE` | `/api/v1/admin/acts/ingest` | bearer | Cancel all running ingestion tasks |
| `POST` | `/api/v1/admin/acts/{slug}/ingest` | bearer | Trigger ingestion for one Act |
| `DELETE` | `/api/v1/admin/acts/{slug}/ingest` | bearer | Cancel one Act's ingestion |
| `GET` | `/api/v1/admin/acts` | bearer | Acts with ingestion state, chunks, run history |
| `GET` | `/api/v1/admin/metrics` | bearer | 24h metrics: decline rate, cache hit, p95 latency, spend |
| `GET` | `/api/v1/admin/queries` | bearer | Recent queries (`?limit=N`) |
| `GET·PUT·DELETE` | `/api/v1/admin/llm` | bearer | Read / override / clear active provider+model |

Full interactive docs: `http://localhost:8000/docs`

---

## Corpus management

```bash
# Register Acts from YAML (idempotent — safe to re-run)
cd apps/api && uv run python -m app.ingestion.registry bootstrap

# Snapshot all 16 Acts from bdlaws (saves raw HTML to data/raw/)
uv run python -m app.ingestion.snapshot

# Snapshot one Act
uv run python -m app.ingestion.snapshot --slug digital-security-act-2018

# Snapshot + crawl all per-section sub-pages (act-{id}/section-{id}.html)
uv run python -m app.ingestion.snapshot --sections

# Force refresh all snapshots (re-crawl bdlaws)
uv run python -m app.ingestion.snapshot --force

# Ingest all Acts from snapshots (Celery tasks)
uv run python -m app.ingestion.registry ingest-all

# Ingest via API
curl -X POST http://localhost:8000/api/v1/admin/acts/ingest \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# Cancel running ingestion
curl -X DELETE http://localhost:8000/api/v1/admin/acts/ingest \
  -H "Authorization: Bearer $BDRAG_ADMIN_BEARER_TOKEN"

# Monitor
docker compose logs -f worker | grep -E "succeeded|failed|chunks"

# Feedback analysis — surface low-quality responses for prompt iteration
uv run python -m app.tools.feedback_report
uv run python -m app.tools.feedback_report --rating not_helpful --limit 10
```

**Adding a new Act:** create `config/acts/<slug>.yaml` with source URLs, run `bootstrap`, snapshot, ingest, add ≥ 4 BN + 4 EN records to `apps/api/eval/dataset/golden.jsonl`, run the eval harness. See [RUNBOOK.md](RUNBOOK.md#8-add-a-new-act).

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

Current schema: 7 tables — `acts`, `provisions`, `provision_revisions`, `chunks`, `ingestion_runs`, `queries`, `feedback`. The `chunks.embedding` column is `halfvec(2560)` with an HNSW index (`halfvec_cosine_ops`).

---

## Development

```bash
# Backend (from apps/api/)
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict app eval
uv run pytest -q
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

# On changes to app/prompts/, app/rag/, app/rag/intent.py, eval/dataset/:
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

Caddy provisions TLS automatically for `$DOMAIN`. All secrets are environment-only. See [RUNBOOK.md](RUNBOOK.md) for day-two operations: bootstrap, ingestion, prompt rollback, disclaimer updates, LLM override, and incident response.

---

## Project structure

```
bd-legal-rag/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── api/            # FastAPI routes + schemas + deps
│   │   │   ├── db/             # Engine, models, Alembic migrations
│   │   │   ├── ingestion/      # crawler, parser, snapshot, tasks, registry
│   │   │   ├── llm/            # Provider protocol (Claude/OpenAI/Ollama), factory, runtime
│   │   │   ├── processing/     # Chunker, embedder (Cohere + Ollama)
│   │   │   ├── prompts/
│   │   │   │   ├── families/
│   │   │   │   │   ├── legal_answer/   # v1, v2 — citation Q&A
│   │   │   │   │   ├── legal_advice/   # v1 — advice with statutory grounding
│   │   │   │   │   └── act_summary/    # v1 — summary + explain
│   │   │   │   └── safety/     # disclaimer.py, decline.py
│   │   │   ├── rag/
│   │   │   │   ├── intent.py       # 5-intent query classifier (EN + BN)
│   │   │   │   ├── act_info.py     # DB-only handlers (section list)
│   │   │   │   ├── postprocessor.py # Strip filler openers
│   │   │   │   ├── retriever.py    # HNSW + FTS + RRF
│   │   │   │   ├── reranker.py     # Cohere mandatory rerank
│   │   │   │   ├── generator.py    # Full pipeline (both paths)
│   │   │   │   ├── citation.py     # Placeholder resolver + markdown links
│   │   │   │   ├── decline_gate.py # Bilingual advice-seeking classifier
│   │   │   │   └── guardrails.py   # Normative-phrase blacklist
│   │   │   ├── seeders/        # acts, corpus, queries, feedback seeders
│   │   │   ├── tools/
│   │   │   │   └── feedback_report.py  # python -m app.tools.feedback_report
│   │   │   └── config.py       # pydantic-settings; all tunables
│   │   ├── eval/
│   │   │   ├── dataset/golden.jsonl   # 84-record bilingual eval set
│   │   │   ├── metrics.py
│   │   │   └── harness.py
│   │   └── tests/              # pytest; all external calls mocked
│   └── web/
│       └── src/
│           ├── pages/          # Dashboard, ActsPage, PlaygroundPage,
│           │                   #   ThreadsPage, ActReaderPage
│           ├── features/       # SourcesRow, RegisterActModal
│           ├── components/     # AppShell, Logo, Badge, Button, Card…
│           ├── api/            # Axios clients (public + admin)
│           └── lib/            # langContext, format, utils
├── config/
│   ├── acts/                   # 16 Act YAML registrations
│   └── bdlaws-acts-index.json  # Full index of 1,556 Acts
├── docs/
│   ├── 01-SRS.md
│   └── 02-Architecture.md
├── .github/
│   └── workflows/              # ci.yml · eval.yml · deploy.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── RUNBOOK.md
├── SECURITY.md
├── docker-compose.yml
└── docker-compose.prod.yml
```

---

## What is genuinely different

If you have built a general-purpose RAG before, five things change in a legal domain:

1. **The disclaimer is application output, not model output** — `generator.py` appends it to every user-visible response including cache-hits, declines, fail-open, and errors. The LLM never sees the disclaimer text. Changing it is eval-gated and versioned in `app/prompts/safety/disclaimer.py`.

2. **Citations are placeholders resolved post hoc** — the LLM emits `{cite:chunk_id}`; `app/rag/citation.py` renders canonical English or Bengali strings with Bengali numeral conversion and wraps each in a markdown link to the source bdlaws page. Any placeholder not in the supplied set is stripped silently.

3. **Rerank is mandatory, not optional** — legal precision demands a cross-encoder pass. The system degrades to `LOW` confidence rather than failing when the reranker is unreachable. Vector-only retrieval is never served as HIGH confidence.

4. **The data model is temporal** — `provision_revisions` records effective windows (`effective_from`, `effective_to`). Every retrieval query includes a mandatory `as_of_date` predicate. A query about the 2010 form of a provision must not serve the 2024 amendment.

5. **Intent routing replaces a single prompt** — five distinct query modes (Q&A, advice, summary, section list, explain) each use a purpose-built prompt and handler. Section lists return directly from the DB with no LLM involved.

---

## Corpus source

All statutory text is sourced from the official Bangladesh law portal maintained by the Ministry of Law, Justice and Parliamentary Affairs:

```
https://bdlaws.minlaw.gov.bd
```

Act pages: `http://bdlaws.minlaw.gov.bd/act-{id}.html` (Bengali) and `?lang=en` (English). Section pages: `http://bdlaws.minlaw.gov.bd/act-{id}/section-{sectionId}.html`. bdlaws IDs for each registered Act are in `config/acts/<slug>.yaml`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — includes the non-negotiable safety rules, where-things-go table, and the eval gate requirement for all RAG/prompt changes.

## Security

See [SECURITY.md](SECURITY.md) — responsible disclosure contact and the security design decisions built into the pipeline.

## License

MIT © 2026 [Al Amin Ahamed](https://github.com/mralaminahamed)
