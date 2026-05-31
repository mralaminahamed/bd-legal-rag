# Bangladesh Legal RAG

[![CI](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/mralaminahamed/bd-legal-rag/actions/workflows/ci.yml)

**Author:** Al Amin Ahamed ([@mralaminahamed](https://github.com/mralaminahamed))

A self-hosted Retrieval-Augmented Generation service that answers questions about Bangladeshi statute
law, grounded in the publicly published text at `bdlaws.minlaw.gov.bd`. v1.0 covers five Acts in
Bengali and English: Companies Act 1994, Income Tax Act 2023, VAT and SD Act 2012, Bangladesh Labour
Act 2006, and Digital Security Act 2018.

> **This is an informational research tool, not legal advice.** Every response carries a mandatory
> bilingual disclaimer. The system declines advice-seeking queries and never states a legal conclusion
> in its own voice.

## How it works

```
question → POST /api/v1/query
  → language detection (Bengali Unicode-block analysis)
  → hybrid retrieve (HNSW cosine + Postgres FTS with effective-date filter, merged by RRF)
  → mandatory rerank (Cohere rerank-multilingual-v3.0)
  → decline gate (advice-seeking? recall too low?)
  → generate (cache → cost breaker → provider → citation validation → guardrails)
  → disclaimer inject (application-controlled — every response, every path)
  → cited, bilingual answer  (or decline / degraded provisions)
```

- **Frameworkless** pgvector RAG — no LangChain/LlamaIndex in the hot path.
- **Bilingual Bengali/English** — Cohere `embed-multilingual-v3.0` at 1024 dims with `input_type`
  asymmetry enforced at the type level. Bengali text is authoritative; English on bdlaws is a
  reference translation.
- **Temporal corpus** — `provision_revisions` track effective windows; retrieval filters by
  `as_of_date` (default today). Ask about the 2010 form of a provision, get the 2010 text.
- **Safety plane** — mandatory bilingual disclaimer (application-controlled, not model-controlled),
  advice-seeking decline gate, normative-conclusion guardrails, canonical citation validator.
- **Multi-provider generation** — Claude, OpenAI, or Ollama, interchangeable by config and
  switchable at runtime from the admin Settings page.
- **Mandatory rerank** — legal precision demands a cross-encoder pass. Degrades to `LOW` confidence
  when the reranker is unreachable; never fails the request.
- **Resilient** — fail-open on provider outage (retrieved provisions + disclaimer); per-request cost
  circuit breaker; content-hash response cache.

See `docs/` for the full SRS, architecture, implementation plan, and ADRs.

## Repository layout

A monorepo: pnpm + Turborepo workspace for the JS apps, with the Python service self-contained
under `apps/api`.

```
apps/
  api/     # Python backend — FastAPI + Celery (package app, eval/, tests/, own pyproject + uv.lock)
  web/     # bilingual search-style web interface (static, no build step)
  admin/   # operator console — Vite + React + TypeScript
config/acts/    # declarative Act registrations (5 v1.0 Acts; see config/README.md)
caddy/          # Caddyfile for production TLS reverse proxy
docker-compose*.yml   pnpm-workspace.yaml   turbo.json
```

Python commands run from `apps/api`; JS commands (`pnpm dev/build`) from the repo root.

## Quickstart (local)

```bash
cd apps/api && uv sync                     # install Python deps (lockfile committed)
docker compose up -d                       # postgres+pgvector, redis, app, worker, beat, web, admin
cd apps/api && uv run alembic upgrade head # apply migrations
curl localhost:8000/health                 # {"status":"ok",...}
```

`docker compose up` runs all services: **api** (`:8000`), worker, beat, Postgres, Redis, the
**web interface** (`web`, `:8080`), and the **admin console** (`admin`, `:8081`).

In production (`docker-compose.prod.yml`) Caddy serves the API + web interface on `$DOMAIN` and
the admin console on `admin.$DOMAIN`, all with automatic TLS.

Set provider keys in `.env` (see `.env.example`):

```
BDRAG_COHERE_API_KEY=...         # embeddings + mandatory reranking (required)
BDRAG_ANTHROPIC_API_KEY=...      # Claude provider (optional)
BDRAG_OPENAI_API_KEY=...         # OpenAI provider (optional)
BDRAG_DEFAULT_PROVIDER=ollama    # generation: anthropic | openai | ollama
BDRAG_OLLAMA_BASE_URL=http://host.docker.internal:11434
BDRAG_ADMIN_BEARER_TOKEN=...     # admin endpoints (required)
```

**Cohere is the only required external API** for core functionality — it handles both embeddings
and mandatory reranking. Generation can run fully local via Ollama.

Generate the admin token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Seed the corpus

Acts are registered declaratively in `config/acts/*.yaml`. Bootstrap and ingest:

```bash
cd apps/api
uv run python -m app.ingestion.registry bootstrap    # seed the five v1.0 Acts
curl -X POST localhost:8000/api/v1/admin/ingest \
  -H "Authorization: Bearer $TOKEN"                  # trigger ingestion for all Acts
docker compose logs -f worker                        # watch progress
```

One Celery task runs per `(act, language)`; a failing task never aborts the others. Unchanged
provisions are skipped by content hash. A Celery beat schedule keeps the corpus fresh.

## Admin console

The `admin` app (`:8081`, `apps/admin`) is a React/TypeScript console for operating the service:

- **Dashboard** — service health, query metrics, corpus coverage, and a recent-activity feed.
- **Acts** — searchable/sortable registry; expand an Act to see its sources and trigger ingestion.
- **Playground** — a bilingual chat-style interface for grounded, cited Q&A (streamed).
- **Settings** — switch the generation provider/model at runtime, test the API connection, profile.

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | — | Liveness + DB/Redis probes |
| POST | `/api/v1/query` | per-IP rate limit | Ask a question; returns a cited answer + disclaimer |
| POST | `/api/v1/query/stream` | per-IP rate limit | Same, streamed as SSE: `token` events then `final` |
| POST | `/api/v1/feedback` | per-IP rate limit | Bind `helpful`/`not_helpful`/`wrong_citation`/`out_of_scope` to a `query_id` |
| GET | `/api/v1/acts` | — | List Acts with status, ministry, snapshot date |
| GET | `/api/v1/acts/{slug}/structure` | — | Statutory tree: Part → Chapter → Section |
| GET | `/api/v1/acts/{slug}/sections/{section}` | — | Provision text + hierarchy_path + disclaimer |
| POST | `/api/v1/admin/ingest` | bearer | Trigger ingestion for all Acts |
| POST | `/api/v1/admin/ingest/{slug}` | bearer | Trigger ingestion for one Act (one task per language) |
| GET | `/api/v1/admin/acts` | bearer | List Acts with source counts and ingestion state |
| GET | `/api/v1/admin/metrics` | bearer | Decline rate, mean confidence, citation accuracy, p95 latency, cache-hit rate, daily spend |
| GET | `/api/v1/admin/queries` | bearer | Recent queries for the activity feed (`?limit=`) |
| GET·PUT·DELETE | `/api/v1/admin/llm` | bearer | Read / override / reset the active generation provider+model |

The streaming endpoint emits provisional `token` events followed by a `final` event carrying the
citation-validated, disclaimer-bearing answer. Clients should replace provisional text with the
`final` event content.

## Production deployment

```bash
DOMAIN=legal.example.com POSTGRES_PASSWORD=… BDRAG_ADMIN_BEARER_TOKEN=… \
BDRAG_COHERE_API_KEY=… BDRAG_ANTHROPIC_API_KEY=… \
docker compose -f docker-compose.prod.yml up -d
```

Caddy terminates TLS automatically for `$DOMAIN`. All secrets are environment-only. See
`RUNBOOK.md` for day-two operations.

## Quality gates

```bash
# Backend (from apps/api)
ruff check . && ruff format --check .     # lint + format
mypy --strict app eval                    # types
pytest                                    # tests (all external calls mocked/VCR-replayed)
python -m eval.harness                   # offline eval gate

# Admin console (from repo root)
pnpm --filter @bd-legal-rag/admin type-check
pnpm --filter @bd-legal-rag/admin lint
pnpm --filter @bd-legal-rag/admin build
pnpm --filter @bd-legal-rag/admin e2e    # Playwright (API mocked)
```

CI runs backend lint/typecheck/test and the admin build on every push. The eval gate runs on
changes under `apps/api/app/prompts/`, `apps/api/app/rag/`, or `apps/api/eval/dataset/` and blocks
regressions below the thresholds: section citation accuracy ≥ 0.85, language routing accuracy ≥
0.95, decline accuracy ≥ 0.95.

## What is genuinely different about this project

If you have built a general-purpose RAG before, four things change here:

1. **The disclaimer is application output, not model output** (ADR-004). Every user-visible
   response — cache-hits, declines, fail-open, errors — is wrapped by
   `apps/api/app/rag/generator.py`'s injector. The LLM never sees the disclaimer.
2. **Citations are placeholders resolved post hoc** (ADR-005). The LLM emits
   `{{cite:chunk_id}}`; `apps/api/app/rag/citation.py` renders canonical English or Bengali
   strings with Bengali numeral conversion. Citation accuracy is testable without model quality.
3. **Rerank is mandatory** (ADR-003). Legal precision demands a cross-encoder pass. When the
   reranker is unreachable, the system degrades to `LOW` confidence rather than failing.
4. **The data model is temporal** (ADR-006). `provision_revisions` track effective windows, and
   retrieval always filters by `as_of_date`. A question about the 2010 form of a provision must
   not be served the 2024 amendment.
