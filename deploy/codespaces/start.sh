#!/bin/bash
# Starts the demo shop (8001) and the API (8000) in the background; safe to run again (it restarts both).
# Secrets (DATABASE_URL, keys, AUTH_SECRET, ...) come from the Codespace's environment.
set -u
cd "$(dirname "$0")/../../backend"
pkill -f "uvicorn qagent.api.main" 2>/dev/null; pkill -f "uvicorn main:app" 2>/dev/null; sleep 1
nohup uv run uvicorn main:app --app-dir ../demo-shop --host 127.0.0.1 --port 8001 --log-level warning > /tmp/qagent-shop.log 2>&1 &
uv run alembic upgrade head > /tmp/qagent-migrate.log 2>&1 || { echo "migration failed, see /tmp/qagent-migrate.log"; tail -5 /tmp/qagent-migrate.log; }
nohup uv run uvicorn qagent.api.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*' > /tmp/qagent-api.log 2>&1 &
for i in $(seq 1 30); do curl -sf localhost:8000/health >/dev/null && { echo "QAgent API is up on port 8000"; exit 0; }; sleep 1; done
echo "API did not start; see /tmp/qagent-api.log"; tail -5 /tmp/qagent-api.log
