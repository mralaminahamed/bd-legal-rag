# Contributing to BD Legal RAG

## Before you start

This is an informational research tool grounded in publicly published Bangladeshi statute
law. The safety machinery — disclaimer injection, decline gate, citation validator,
guardrails — is load-bearing. Changes to these components require the eval harness to
pass before merge.

Read `docs/01-SRS.md` for the requirements (FR-*/NFR-* identifiers used in code comments)
and `docs/02-Architecture.md` for architectural decisions (ADR-*).

---

## Development setup

**Prerequisites:** Docker, Python 3.12+, Node.js 20+, pnpm, uv

```bash
git clone https://github.com/mralaminahamed/bd-legal-rag.git
cd bd-legal-rag

# Start infrastructure
docker compose up -d

# API
cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m app.seeders          # seed sample data

# Web admin console
cd apps/web
pnpm install
pnpm dev
```

---

## Quality gates

Every PR must pass locally before pushing:

```bash
# API
cd apps/api
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict app eval
uv run pytest -q

# Web
cd apps/web
pnpm type-check
pnpm build
```

The CI workflow runs all four gates plus the eval harness. The eval harness is gated
separately (`eval.yml`) and must pass for any change touching the retrieval or generation
path.

---

## Non-negotiable rules

These apply to every PR without exception:

1. **Disclaimer on every response path.** `disclaimer.inject()` must be called at the
   end of `generator.py`'s response builder. No new response path may bypass it.

2. **No legal conclusions in the system's own voice.** Every normative statement in a
   response must be attributed to a cited provision.

3. **Bengali is authoritative.** The English text on bdlaws is a reference translation.
   When a chunk's `translation_status` is `reference_translation`, the response must
   surface this.

4. **Effective-date filter always applied.** Any retrieval code path that queries chunks
   must include the `pr.effective_from <= :aod AND (pr.effective_to IS NULL OR
   pr.effective_to >= :aod)` predicate.

5. **`input_type` discriminator enforced.** `search_document` at ingest; `search_query`
   at query time. Mixing them silently halves retrieval quality (ADR-002).

6. **No stubs, no `# TODO`, no placeholders.** Every function body must be complete and
   runnable before merge.

7. **mypy --strict clean.** No `Any` escapes, no `# type: ignore` without a justifying
   comment referencing why the stub is absent.

---

## What belongs where

| Area | Location | Notes |
|---|---|---|
| Runtime tunables | `apps/api/app/config.py` | Never hard-code elsewhere |
| DB models | `apps/api/app/db/models.py` | Every schema change needs an Alembic migration |
| Prompt text | `apps/api/app/prompts/` | Versioned; update `registry.py` |
| Disclaimer text | `apps/api/app/prompts/safety/disclaimer.py` | Versioned; eval-gated |
| Citation formatting | `apps/api/app/rag/citation.py` | Only here — nowhere else |
| New Act | `config/acts/<slug>.yaml` | Then `python -m app.ingestion.registry bootstrap` |
| New LLM provider | `apps/api/app/llm/<name>.py` + `factory.py` | Thin: timeout, retry, error mapping |

---

## Commit style

```
type(scope): short description

Longer explanation if needed. Reference requirement IDs:
- FR-GN-6: disclaimer on every path
- ADR-002: embed input_type discriminator
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

---

## Pull request process

1. Branch from `main`. Name: `feat/<description>` or `fix/<description>`.
2. Run all quality gates locally.
3. For retrieval/generation/safety changes, run `uv run python -m eval.harness` and
   paste the output in the PR description.
4. Reference the SRS requirement IDs your change implements or fixes.
5. One reviewer approval required before merge.

---

## Legal domain notes

- **Not legal advice.** The system is an informational research tool. The disclaimer
  text is not decorative — it is a legal requirement of the project.
- **Source attribution.** All statutory text originates from `bdlaws.minlaw.gov.bd`,
  the official publication of the Ministry of Law, Justice and Parliamentary Affairs of
  Bangladesh.
- **Amendment tracking.** When adding a provision revision, set `amending_act_id` and
  `effective_from`/`effective_to` accurately. Do not truncate the entire act on a
  single-revision update.
