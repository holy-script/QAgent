#!/bin/bash
# Starts every process of the single-container deployment and stops the container if any of them dies.
set -u
cd /app/backend
uv run uvicorn main:app --app-dir /app/demo-shop --host 127.0.0.1 --port 8001 --log-level warning &
(uv run alembic upgrade head && exec uv run uvicorn qagent.api.main:app --host 127.0.0.1 --port 8000 --workers 1) &
(cd /app/web && exec node node_modules/next/dist/bin/next start -p 3000 -H 127.0.0.1) &
caddy run --config /app/Caddyfile --adapter caddyfile &
wait -n
echo "a process exited; stopping" >&2
exit 1
