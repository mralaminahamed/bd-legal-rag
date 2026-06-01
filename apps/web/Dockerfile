# syntax=docker/dockerfile:1.7

# ==============================================================================
# Bangladesh Legal RAG — Web Image
# ------------------------------------------------------------------------------
# Author : Al Amin Ahamed
# File   : apps/web/Dockerfile
# Stages :
#   - deps    : installs pnpm dependencies (cached layer)
#   - dev     : runs Vite dev server with HMR, used by docker-compose dev
#   - build   : produces optimised static bundle in /app/dist
#   - runtime : nginx:alpine serving the static bundle
#
# The frontend is a static asset bundle in production. nginx serves dist/
# directly; the API image is never involved in frontend delivery.
# ==============================================================================


# ------------------------------------------------------------------------------
# Stage 1 — deps : install dependencies (deterministic, cached).
# ------------------------------------------------------------------------------
FROM node:24-alpine AS deps

# Enable corepack for pnpm; pin version to match package.json packageManager field.
RUN corepack enable && corepack prepare pnpm@10.33.3 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./

# Monorepo root pnpm-workspace.yaml is outside this build context.
# Inline a minimal workspace config so pnpm approves the build scripts.
RUN printf 'packages:\n  - "."\nonlyBuiltDependencies:\n  - esbuild\n' > pnpm-workspace.yaml

ENV CI=true

RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --no-frozen-lockfile


# ------------------------------------------------------------------------------
# Stage 2 — dev : Vite dev server with HMR. Source code mounted at runtime.
# ------------------------------------------------------------------------------
FROM deps AS dev

EXPOSE 5174

# Run vite directly (not via pnpm) to avoid the lockfile pre-flight check.
# The host volume mounts apps/web/pnpm-lock.yaml which may differ from the
# workspace root lockfile; bypassing pnpm avoids ERR_OUTDATED_LOCKFILE.
CMD ["./node_modules/.bin/vite", "--host", "0.0.0.0", "--port", "5174"]


# ------------------------------------------------------------------------------
# Stage 3 — build : produce minified, hashed, tree-shaken bundle in /app/dist.
# ------------------------------------------------------------------------------
FROM deps AS build

# Vite inlines VITE_* env vars at build time.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG VITE_ADMIN_TOKEN
ENV VITE_ADMIN_TOKEN=${VITE_ADMIN_TOKEN}

COPY . .

RUN pnpm run build


# ------------------------------------------------------------------------------
# Stage 4 — runtime : nginx:alpine serving the built bundle.
# ------------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Replace default nginx config with SPA-aware one (handles client-side routing).
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the static bundle from the build stage.
COPY --from=build /app/dist /usr/share/nginx/html

# Pre-create cache directories with correct ownership.
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
