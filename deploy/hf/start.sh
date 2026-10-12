#!/bin/bash
# Starts the demo shop (background) and the API (foreground, port 7860). One worker: live run events are kept in memory.
set -eu
cd /app/backend
uv run uvicorn main:app --app-dir /app/demo-shop --host 127.0.0.1 --port 8001 --log-level warning &
uv run alembic upgrade head
exec uv run uvicorn qagent.api.main:app --host 0.0.0.0 --port 7860 --workers 1 --proxy-headers --forwarded-allow-ips='*'
