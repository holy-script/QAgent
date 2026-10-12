#!/bin/bash
# Starts the demo shop (8001) and the API (8000) in the background; safe to run again (it restarts both).
# Secrets (DATABASE_URL, keys, AUTH_SECRET, ...) come from the Codespace's environment.
set -u
cd "$(dirname "$0")/../../backend"
pkill -f "uvicorn qagent.api.main" 2>/dev/null; pkill -f "uvicorn main:app" 2>/dev/null; sleep 1
setsid nohup uv run uvicorn main:app --app-dir ../demo-shop --host 127.0.0.1 --port 8001 --log-level warning > /tmp/qagent-shop.log 2>&1 &
uv run alembic upgrade head > /tmp/qagent-migrate.log 2>&1 || { echo "migration failed, see /tmp/qagent-migrate.log"; tail -5 /tmp/qagent-migrate.log; }
setsid nohup uv run uvicorn qagent.api.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*' > /tmp/qagent-api.log 2>&1 &
# Make the port public again after every (re)start. Needs a token with the "codespace" scope as the Codespaces secret GH_PAT.
if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GH_PAT:-}" ] && command -v gh >/dev/null; then
  GITHUB_TOKEN="$GH_PAT" gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >/dev/null 2>&1 && echo "port 8000 is public" || echo "could not set port 8000 public (check GH_PAT)"
fi
for i in $(seq 1 30); do curl -sf localhost:8000/health >/dev/null && { echo "QAgent API is up on port 8000"; exit 0; }; sleep 1; done
echo "API did not start; see /tmp/qagent-api.log"; tail -5 /tmp/qagent-api.log
# Leave a redacted status page on the port so a failed start can be diagnosed from outside the Codespace.
mkdir -p /tmp/status && { echo "QAgent API failed to start"; for f in /tmp/qagent-migrate.log /tmp/qagent-api.log /tmp/qagent-shop.log; do echo "== $f"; tail -25 "$f" 2>/dev/null | sed -E 's#(://)[^/@ ]*@#\1***@#g; s#(KEY|SECRET|TOKEN|PASSWORD)[^ ]*#\1=***#gI'; done; } > /tmp/status/index.html
setsid nohup python3 -m http.server 8000 --directory /tmp/status > /dev/null 2>&1 &
