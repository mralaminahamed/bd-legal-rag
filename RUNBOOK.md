# Operator Runbook

**Project:** Bangladesh Legal RAG · **Author:** Al Amin Ahamed

Day-two operations: bootstrap the corpus, trigger ingestion, query, read metrics, and roll back
a prompt or disclaimer version. All admin calls require the bearer token from
`BDRAG_ADMIN_BEARER_TOKEN`.

## 0. Generate the admin token

`BDRAG_ADMIN_BEARER_TOKEN` is an opaque, high-entropy secret; the API compares the
`Authorization` header to `Bearer <token>` exactly. Generate one and supply it via the
environment (never commit it — `.env` is git-ignored):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # or: openssl rand -base64 32
```

```bash
# local
echo "BDRAG_ADMIN_BEARER_TOKEN=<generated>" >> .env && docker compose up -d app
# production: set in your secrets manager / host env before `up`
```

Without it, all `/api/v1/admin/*` endpoints return 401.

## Session variables

```bash
export API=http://localhost:8000
export TOKEN=your-admin-bearer-token
```

## 1. Bootstrap and seed the Acts

Acts are registered declaratively in `config/acts/*.yaml`. Seed them into the database:

```bash
cd apps/api
BDRAG_DATABASE_DSN=postgresql+asyncpg://bdrag:bdrag@localhost:5432/bdrag \
  uv run python -m app.ingestion.registry bootstrap
```

Verify Acts are registered (16 as of v1.0):

```bash
curl -sS "$API/api/v1/admin/acts" -H "Authorization: Bearer $TOKEN"
# → [{"slug":"labour-act-2006","source_count":2,"status":"in_force",...}, ...]
```

## 2. Ingest the corpus

```bash
# Ingest all Acts (one Celery task per (act, language)):
curl -sS -X POST "$API/api/v1/admin/acts/ingest" -H "Authorization: Bearer $TOKEN"
# → {"task_ids":[...],"message":"Dispatched 32 ingestion tasks for 16 acts."}

# Or ingest a single Act:
curl -sS -X POST "$API/api/v1/admin/acts/labour-act-2006/ingest" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json"
```

A failing task never aborts other tasks. Unchanged provisions are skipped by content hash. Watch
progress:

```bash
docker compose logs -f worker
```

Inspect an Act's last-ingested state:

```bash
curl -sS "$API/api/v1/admin/acts" -H "Authorization: Bearer $TOKEN"
```

Re-run ingestion anytime — only changed provisions are re-embedded. A Celery beat schedule
keeps the corpus fresh automatically.

## 3. Query

```bash
# Informational query (Bengali)
curl -sS -X POST "$API/api/v1/query" -H "Content-Type: application/json" \
  -d '{"question":"শ্রম আইনে সাপ্তাহিক ছুটির বিধান কী?","act_slug":"labour-act-2006"}'

# Informational query (English, with temporal filter)
curl -sS -X POST "$API/api/v1/query" -H "Content-Type: application/json" \
  -d '{"question":"What is the weekly holiday provision?",
       "act_slug":"labour-act-2006","as_of_date":"2010-01-01"}'

# Advice-seeking query (will be declined)
curl -sS -X POST "$API/api/v1/query" -H "Content-Type: application/json" \
  -d '{"question":"Should I sue my employer for unpaid wages?"}'
# → {"declined":true,"answer":"...","disclaimer":"..."}
```

Responses always carry `disclaimer` (application-controlled). Key flags:

- `degraded: true` — LLM unreachable; provisions + citations + disclaimer returned, no summary.
- `declined: true` — advice-seeking query or recall too low; canonical bilingual decline text.
- `confidence: "LOW" | "MEDIUM" | "HIGH"` — tiered from rerank scores.
- `cached: true` — served from content-hash cache.

Stream the answer as Server-Sent Events:

```bash
curl -sS -N -X POST "$API/api/v1/query/stream" -H "Content-Type: application/json" \
  -d '{"question":"What is Section 103 of the Labour Act?"}'
# event: token  → incremental deltas (provisional)
# event: final  → {answer, citations, disclaimer, query_id, ...}  (citation-validated)
```

Submit feedback:

```bash
curl -sS -X POST "$API/api/v1/feedback" -H "Content-Type: application/json" \
  -d '{"query_id":"<uuid>","rating":"wrong_citation","comment":"Section number incorrect"}'
```

## 4. Monitor

```bash
# Service metrics
curl -sS "$API/api/v1/admin/metrics" -H "Authorization: Bearer $TOKEN"
# decline_rate, mean_confidence_by_category, citation_accuracy_by_act, p95_latency_ms, cache_hit_rate, daily_spend_usd

# Recent activity feed
curl -sS "$API/api/v1/admin/queries?limit=20" -H "Authorization: Bearer $TOKEN"

# Health + dependency reachability
curl -sS "$API/health"
# {"status":"ok","db":"ok","redis":"ok"}
```

## 5. Roll back a prompt version

All prompt versions ship together in `apps/api/app/prompts/families/legal_answer/`. Roll back by
changing `status` to `"active"` on the prior version and setting the new version to
`"candidate"` in code, then:

```bash
cd apps/api
git diff app/prompts/          # inspect the change
uv run python -m eval.harness  # eval must pass before merging
```

The active version is resolved at runtime from the registry; no restart is needed after a deploy.

## 6. Update the disclaimer

1. Add a new `Disclaimer` version to `apps/api/app/prompts/safety/disclaimer.py` (both `bn` and
   `en` text, a `changelog` entry, `status="active"`; old version → `status="retired"`).
2. Flip `active_disclaimer_version` in `apps/api/app/config.py`.
3. Run the full test suite — the parametrised disclaimer test covers every response path.
4. Run `python -m eval.harness` — disclaimer changes are eval-gated.
5. Deploy. The new disclaimer appears on every subsequent response including cache-hits (the cache
   layer re-asserts the active version and refreshes stale entries).

## 7. Override the LLM provider at runtime

Switch provider without a restart (useful during an incident):

```bash
# Switch to OpenAI:
curl -sS -X PUT "$API/api/v1/admin/llm" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","model":"gpt-4o-mini"}'

# Check what is active:
curl -sS "$API/api/v1/admin/llm" -H "Authorization: Bearer $TOKEN"
# → {"provider":"openai","model":"gpt-4o-mini","source":"override"}

# Revert to env default:
curl -sS -X DELETE "$API/api/v1/admin/llm" -H "Authorization: Bearer $TOKEN"
```

The override is stored in Redis (`llm:override` key). A missing or malformed key falls back to
the env-file defaults — a stale override can never wedge generation.

## 8. Add a new Act to the corpus

1. Create `config/acts/<slug>.yaml` following the schema in `config/README.md`.
2. Sync and ingest:

   ```bash
   cd apps/api
   uv run python -m app.ingestion.registry bootstrap   # picks up the new YAML
   curl -X POST "$API/api/v1/admin/ingest/<slug>" -H "Authorization: Bearer $TOKEN"
   ```

3. Add ≥ 4 BN + 4 EN golden records to `apps/api/eval/dataset/golden.jsonl`.
4. Run `python -m eval.harness` — thresholds must still hold with the expanded corpus.

## 9. Investigate a wrong_citation feedback report

```bash
# Get the original query record
curl -sS "$API/api/v1/admin/queries?limit=50" -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.id=="<query_id>")'

# Fields to inspect:
# retrieved_chunk_ids — the chunks supplied to the model
# rerank_top_score — confidence of top chunk
# prompt_version — which prompt rendered the context
# declined / degraded / confidence_tier
```

A wrong citation means a `{{cite:chunk_id}}` placeholder was rendered for a chunk the model
cited but which did not belong to the supplied set — this should be impossible if citation
validation is working. Check that `apps/api/app/rag/citation.py` is stripping foreign
placeholders and investigate the specific `query_id` for how the chunk slipped through.

## Common issues

| Symptom | Likely cause | Action |
|---|---|---|
| `degraded: true` | Cohere or LLM key missing/invalid | check `BDRAG_COHERE_API_KEY` and `BDRAG_*_API_KEY` |
| `declined: true` for informational query | corpus not yet ingested | run bootstrap + ingestion |
| No chunks returned | `as_of_date` too early / corpus not ingested | trigger ingestion; check `effective_from` dates |
| 401 on admin calls | wrong/missing bearer token | set `BDRAG_ADMIN_BEARER_TOKEN` |
| 429 on `/query` | rate limit hit | tune `BDRAG_RATE_LIMIT_MAX_REQUESTS` |
| cost breaker refuses a call | projected cost over ceiling | raise `BDRAG_COST_CEILING_USD_PER_REQUEST` |
| Retrieval misses Bengali text | `input_type` mixup at embed time | verify `EmbedInputType.SEARCH_DOCUMENT` used at ingest |
| Disclaimer missing from response | new code path bypasses injector | check generator pipeline; disclaimer must run on every path |

## Serving through a Cloudflare Tunnel

`docker-compose.prod.yml` is the stack. `docker-compose.tunnel.yml` changes how it is reached:
nothing is published except Caddy on `127.0.0.1:8101`, so the tunnel connector is the only thing
facing the internet. The project is `bd-legal-rag-prod`, separate from the dev stack's
`bd-legal-rag`, so the two never share a Postgres volume (a volume keeps the password it was
created with).

```bash
cp .env.tunnel.example .env.tunnel          # then fill in the two secrets: openssl rand -hex 32
docker compose --env-file .env.tunnel -f docker-compose.prod.yml -f docker-compose.tunnel.yml up -d --build
docker exec bd-legal-rag-prod-app-1 python -m app.ingestion.registry bootstrap
```

`--env-file` is required. Without it compose reads the development `.env`, whose admin token is
`dev-admin-token`.

What the overlay does, and why each piece is there:

| Piece | Reason |
|---|---|
| `migrate` service | The prod stack had no migration step; an empty database answers 500 on the first query. |
| `--proxy-headers --forwarded-allow-ips <private ranges>` | The rate limit keys on the caller's address. Behind Caddy that is Caddy, so 6 visitors sent 24 requests and shared one bucket of 20 (measured). With the ranges trusted, each visitor has their own and a forged leftmost `X-Forwarded-For` entry does not help. `*` is wrong the other way: it trusts the leftmost entry, which the visitor writes. |
| `Caddyfile.tunnel` `trusted_proxies` | Same reason, one hop earlier. Caddy replaces `X-Forwarded-For` with the peer address unless it trusts the peer. |
| `@private_threads` | `GET /api/v1/threads` and `/api/v1/thread/{id}` need no authentication and return every visitor's questions and answers. On a public origin they need the admin token. A stopgap: the endpoints should require it themselves. |
| `snapshots` volume, `/app/data` owned by `bdrag` | The worker saves the bdlaws HTML it crawls. The directory was root's, so every ingest task ended `status: failed` while Celery reported the task as succeeded. |

The console sends the admin token once it is entered under Settings. Read it with
`grep BDRAG_ADMIN_BEARER_TOKEN .env.tunnel`.

### Before this is public

Measured on 24 September 2026. The deployment does not fix any of these.

1. **The corpus has no statute text, and nothing can put it there yet.** The main page of each
   Act on bdlaws is a table of contents, so the chunks read "1. Short title, extent and
   commencement" under hierarchy paths like `Part ?`. The text is on the per-section pages, which
   `python -m app.ingestion.snapshot --sections` saves under `data/raw/{slug}/sections/{lang}/`,
   4,018 pages across the 16 Acts. But `ingestion/tasks.py` reads only `{lang}.html`, and no code
   reads the section snapshots: there is no parser for a section page and no task that attaches
   its text to the tree. Crawling more changes nothing until that exists.
2. **Each Act is published in one language, not two.** `?lang=en` returns the same page as no
   parameter, and `?lang=bn` only translates the site's own navigation. For the five newer Acts
   (Companies 1994, Digital Security 2018, Income Tax 2023, Labour 2006, VAT and SD 2012) the text
   is Bengali. For the eleven older ones it is English. `config/acts/*.yaml` listed both languages
   for all 16, so every Act was stored twice under two labels, one of them false. Each now lists
   only the language it is published in. The English text of the five Bengali Acts is not on the
   portal. `translation_status` is still derived from the language label alone
   (`tasks.py`: `bn` is authoritative, `en` is a reference translation), which calls the
   original English enactments reference translations.
3. **An advice-seeking question is answered, not declined.** Commit `33e0117` routes
   "should I", "can I", "my rights" and their Bengali forms to a `legal_advice` prompt and skips
   the decline gate for them (`generator.py`, `_bypass_decline`). The project rules say the
   opposite (CLAUDE.md rule 3, NFR-LS-3), and four tests written for that rule fail:
   `test_advice_seeking_en_declines_NFR_LS_3`, `..._bn_...`,
   `test_disclaimer_present_on_decline_response_NFR_LS_1` and
   `test_circuit_breaker_refuses_oversized_request`. That one also reaches a live provider, so
   it passes or fails on what your `.env` says. This is a policy decision and has not been
   touched.
4. **The admin ingest endpoints and the beat schedule dispatch both languages for every Act**,
   so an Act with one source reports a `failed` run for the language it does not have.
5. **Crawl politely.** The crawler sleeps `1 / BDRAG_BDLAWS_RATE_LIMIT_RPS` before each request
   but runs three at once, so the default 1.0 is about 2 to 3 requests a second in total. With
   `BDRAG_BDLAWS_RATE_LIMIT_RPS=0.34` it measured 60 pages in 82 seconds. `robots.txt` on the
   portal is a 404, so nothing there restricts it.
