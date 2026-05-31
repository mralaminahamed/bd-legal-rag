# syntax=docker/dockerfile:1
# Bangladesh Legal RAG — Admin web image. Author: Al Amin Ahamed.
# Multi-stage: install deps, build the Vite bundle, serve via nginx.

FROM node:24-alpine AS deps
RUN corepack enable && corepack prepare pnpm@10.33.3 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
# Standalone build context: declare a single-package workspace.
RUN printf 'packages:\n  - "."\nonlyBuiltDependencies:\n  - esbuild\n' > pnpm-workspace.yaml
ENV CI=true
RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --no-frozen-lockfile

FROM deps AS build
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY . .
RUN pnpm run build

FROM nginx:1.27-alpine AS runtime
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
