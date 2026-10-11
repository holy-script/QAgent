# Same Python, same Playwright, same Chromium everywhere. Build from the repo root:
#   docker build -f backend/Dockerfile -t qagent-api .
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/
COPY backend/qagent ./backend/qagent
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini
COPY playbooks ./playbooks
WORKDIR /app/backend
RUN uv sync --frozen --no-dev && uv run playwright install chromium
ENV QAGENT_HEADLESS=true
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "qagent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
