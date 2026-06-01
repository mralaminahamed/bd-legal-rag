# syntax=docker/dockerfile:1.7

# ==============================================================================
# Bangladesh Legal RAG — API Image
# ------------------------------------------------------------------------------
# Author : Al Amin Ahamed
# File   : apps/api/Dockerfile
# Build context : repo root (docker-compose sets context: .)
# Stages :
#   - base    : shared OS + Python + uv setup
#   - deps    : installs production dependencies into a venv
#   - dev     : adds dev dependencies, retains uv, used by docker-compose dev
#   - runtime : minimal production image, copies venv only, runs as non-root
#
# Single image used by the api, worker, and beat services; the container command
# (uvicorn vs celery) is supplied by the orchestrator, not baked into the image.
# Dependencies installed with uv against the committed lockfile (NFR-PT-1).
# ==============================================================================


# ------------------------------------------------------------------------------
# Stage 1 — base
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    # config/acts/ is copied to /app/config/acts in the runtime stage.
    BDRAG_ACTS_CONFIG_DIR=/app/config/acts

# System dependencies:
#   - libpq5       : psycopg runtime (shared lib)
#   - curl         : healthchecks
#   - tini         : proper PID-1 / signal forwarding for Celery workers
#   - ca-certificates : TLS for Cohere / Anthropic / OpenAI
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libpq5 \
        tini \
 && rm -rf /var/lib/apt/lists/*

# uv — fast Python package manager, pinned for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /usr/local/bin/uv

WORKDIR /app


# ------------------------------------------------------------------------------
# Stage 2 — deps : install production dependencies into a virtualenv.
# ------------------------------------------------------------------------------
FROM base AS deps

# Build toolchain only in this stage — never reaches runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy only dependency manifests first to maximise Docker layer cache.
# Build context is the repo root; source files are under apps/api/.
COPY apps/api/pyproject.toml apps/api/uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# ------------------------------------------------------------------------------
# Stage 3 — dev : adds dev dependencies, used by docker-compose for local work.
#               Application code is bind-mounted at runtime; not COPY'd here.
# ------------------------------------------------------------------------------
FROM deps AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
# No CMD — supplied by docker-compose (uvicorn --reload, celery worker, celery beat).


# ------------------------------------------------------------------------------
# Stage 4 — runtime : minimal production image.
# ------------------------------------------------------------------------------
FROM base AS runtime

# Create unprivileged user.
RUN groupadd --system --gid 1000 bdrag \
 && useradd --system --uid 1000 --gid bdrag --home-dir /app --shell /bin/bash bdrag

# Copy the prebuilt venv from deps stage — no compilers in final image.
COPY --from=deps --chown=bdrag:bdrag /app/.venv /app/.venv

# Copy application source last (most-frequently-changed layer).
COPY --chown=bdrag:bdrag apps/api/app ./app
COPY --chown=bdrag:bdrag apps/api/eval ./eval
COPY --chown=bdrag:bdrag apps/api/alembic.ini ./alembic.ini

# Act registry YAML — required by app.ingestion.registry at startup.
COPY --chown=bdrag:bdrag config/acts ./config/acts

USER bdrag
WORKDIR /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
