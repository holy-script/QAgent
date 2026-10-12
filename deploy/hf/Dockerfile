# Everything in ONE container, for Hugging Face Spaces (which run a single container on one port, 7860).
# Inside: Caddy (7860) -> /api to the backend (8000), everything else to the web app (3000); the demo shop (8001) too.
# Built from the repository root by deploy/hf/publish.sh.

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY frontend ./
ENV NEXT_PUBLIC_API_URL=/api
RUN npm run build

FROM caddy:2 AS caddy

# Same Playwright and Chromium build as everywhere else (pinned to the version in backend/uv.lock).
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends bash && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/
COPY backend/qagent ./backend/qagent
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini
COPY playbooks ./playbooks
COPY demo-shop ./demo-shop
RUN cd backend && uv sync --frozen --no-dev

COPY --from=web /web/.next ./web/.next
COPY --from=web /web/node_modules ./web/node_modules
COPY --from=web /web/package.json ./web/package.json
COPY --from=web /web/public ./web/public
COPY --from=web /web/next.config.ts ./web/next.config.ts
COPY deploy/Caddyfile.hf ./Caddyfile
COPY deploy/hf/start.sh ./start.sh

# Spaces run the container as user 1000.
RUN chmod +x start.sh && chown -R 1000:1000 /app
USER 1000
ENV UV_NO_SYNC=1 HOME=/tmp QAGENT_HEADLESS=true AUTH_COOKIE_SECURE=true UV_CACHE_DIR=/tmp/uv NEXT_TELEMETRY_DISABLED=1
EXPOSE 7860
CMD ["./start.sh"]
