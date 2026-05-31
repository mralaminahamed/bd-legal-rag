# bd-legal-rag — API service

The Python backend (FastAPI + Celery) for the Bangladesh Legal RAG. Package root is `app`; the
offline eval harness lives in `eval`. See the repository root `README.md` for the full project
overview and `RUNBOOK.md` for operations.

```bash
uv sync                          # install (run from this directory)
uv run alembic upgrade head      # migrate
uv run uvicorn app.main:app --reload
uv run ruff check . && uv run mypy --strict app eval && uv run pytest
uv run python -m eval.harness
```

Author: Al Amin Ahamed.
