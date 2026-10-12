# The API (with its Chromium) as ONE container for Hugging Face Spaces, which expose a single port (7860).
# The web app lives on Vercel and reaches this API through a /api rewrite (see frontend/next.config.ts).
# The demo shop runs inside the same container on 127.0.0.1:8001, so "Demo Shop" works with no extra hosting.
# Built from the repository root by deploy/hf/publish.sh.

# Same Playwright and Chromium build as everywhere else (pinned to the version in backend/uv.lock).
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends bash && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
# The base image's Python is 3.10; the backend needs 3.11+. Pin one with prebuilt wheels, in a place user 1000 can read.
ENV UV_PYTHON=3.12 UV_PYTHON_INSTALL_DIR=/opt/python

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/
COPY backend/qagent ./backend/qagent
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini
COPY playbooks ./playbooks
COPY demo-shop ./demo-shop
RUN cd backend && uv sync --frozen --no-dev
COPY deploy/hf/start.sh ./start.sh

# Spaces run the container as user 1000.
RUN chmod +x start.sh && chown -R 1000:1000 /app && chmod -R a+rX /opt/python
USER 1000
ENV UV_NO_SYNC=1 HOME=/tmp QAGENT_HEADLESS=true AUTH_COOKIE_SECURE=true UV_CACHE_DIR=/tmp/uv
EXPOSE 7860
CMD ["./start.sh"]
