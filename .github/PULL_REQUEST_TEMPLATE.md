## What this PR does

<!-- One or two sentences. -->

## Requirement IDs

<!-- List FR-* or NFR-* IDs from docs/01-SRS.md that this PR implements or fixes. -->
<!-- Remove this section if not applicable. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behaviour change)
- [ ] Docs / config only
- [ ] Breaking change

## Quality gates

Run these locally before requesting review:

```bash
# API
cd apps/api
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict app eval
uv run pytest -q

# Web (if changed)
cd apps/web
pnpm type-check && pnpm build
```

- [ ] `ruff check` clean
- [ ] `mypy --strict` clean
- [ ] `pytest` green
- [ ] Web type-check + build clean (if `apps/web/` changed)

## Eval harness (retrieval / generation / safety changes only)

If this PR touches `app/rag/`, `app/prompts/`, `app/processing/`, or disclaimer/decline
text, paste the eval output here:

```
# uv run python -m eval.harness
```

- [ ] Section citation accuracy ≥ 0.85
- [ ] Language routing accuracy ≥ 0.95
- [ ] Decline accuracy ≥ 0.95

## Safety checklist (legal domain)

- [ ] `disclaimer.inject()` is called on every new response path
- [ ] No new code emits legal conclusions in the system's own voice
- [ ] Effective-date predicate applied in any new retrieval query
- [ ] Citation validator strips foreign placeholders (no LLM-fabricated citations)

## Notes for reviewer

<!-- Anything the reviewer should know: trade-offs, known limitations, follow-up work. -->
