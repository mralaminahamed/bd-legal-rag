# syntax=docker/dockerfile:1
# Bangladesh Legal RAG — application image.
# Author: Al Amin Ahamed.
#
# Single image used by the api, worker, and beat services; the command differs
# per service in docker-compose. Dependencies are installed with uv against the
# committed lockfile for reproducible builds (NFR-PT-1).

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# uv: pinned copy from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first, against the lockfile, for layer caching.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Application source.
COPY app ./app
COPY eval ./eval
COPY alembic.ini ./alembic.ini

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Default command runs the API; worker/beat override this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
