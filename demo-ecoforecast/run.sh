#!/usr/bin/env bash
# EcoForecast demo launcher: backend on 8010, frontend on 3010.
# Usage: ./run.sh [start|stop|status|restart]      (default: start)
# Env overrides: BE_PORT, FE_PORT, ADMIN_USERNAME, ADMIN_PASSWORD, FE_MODE=start|dev
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BE_DIR="$HERE/Ecosystem-Forecast-Backend-main"
FE_DIR="$HERE/Ecosystem-Forecast-main"
VENV="$HERE/.venv-eco"
RUN_DIR="$HERE/.run"
BE_PORT="${BE_PORT:-8010}"
FE_PORT="${FE_PORT:-3010}"
FE_MODE="${FE_MODE:-start}"
mkdir -p "$RUN_DIR"

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

kill_tree() { # kill a pid file's process and its children
  local f="$1"
  [ -f "$f" ] || return 0
  local pid; pid="$(cat "$f")"
  pkill -TERM -P "$pid" 2>/dev/null
  kill -TERM "$pid" 2>/dev/null
  rm -f "$f"
}

stop_all() {
  kill_tree "$RUN_DIR/frontend.pid"
  kill_tree "$RUN_DIR/backend.pid"
  # Anything still holding our ports (e.g. next-server child) is ours by construction of the ports.
  for p in "$FE_PORT" "$BE_PORT"; do
    pids="$(lsof -ti tcp:"$p" -sTCP:LISTEN 2>/dev/null || true)"
    [ -n "$pids" ] && kill $pids 2>/dev/null
  done
  echo "stopped"
}

status() {
  for n in backend frontend; do
    if alive "$RUN_DIR/$n.pid"; then echo "$n running, pid $(cat "$RUN_DIR/$n.pid")"; else echo "$n not running"; fi
  done
}

wait_http() { # url, seconds
  local i=0
  until curl -fsS -o /dev/null "$1" 2>/dev/null; do
    i=$((i+1)); [ "$i" -ge "$2" ] && return 1; sleep 1
  done
}

start_all() {
  if alive "$RUN_DIR/backend.pid" || alive "$RUN_DIR/frontend.pid"; then
    echo "already running (use ./run.sh stop first)"; status; exit 1
  fi
  for p in "$BE_PORT" "$FE_PORT"; do
    if lsof -ti tcp:"$p" -sTCP:LISTEN >/dev/null 2>&1; then echo "port $p is already in use"; exit 1; fi
  done

  # ---- backend deps
  if [ ! -x "$VENV/bin/python" ]; then
    echo "creating venv $VENV"; python3 -m venv "$VENV" || exit 1
  fi
  if ! "$VENV/bin/python" -c "import fastapi, uvicorn, statsmodels, pmdarima, pptx, boto3, jwt, multipart" 2>/dev/null; then
    echo "installing backend requirements (a few minutes the first time)"
    "$VENV/bin/pip" install -q -r "$BE_DIR/requirements.txt" || exit 1
  fi
  # ---- frontend deps
  if [ ! -d "$FE_DIR/node_modules/next" ]; then
    echo "installing frontend packages"; (cd "$FE_DIR" && npm ci) || exit 1
  fi

  # ---- backend
  # No AWS credentials: the chat copilot (Aria) needs Bedrock and will answer with an error; everything else works.
  (
    cd "$BE_DIR" || exit 1
    export ALLOWED_ORIGINS="http://localhost:$FE_PORT,http://127.0.0.1:$FE_PORT"
    exec "$VENV/bin/python" -m uvicorn main:app --host 127.0.0.1 --port "$BE_PORT"
  ) > "$RUN_DIR/backend.log" 2>&1 &
  echo $! > "$RUN_DIR/backend.pid"

  # ---- frontend (NEXT_PUBLIC_* are inlined at build time, so they must be set for the build too)
  export NEXT_PUBLIC_API_URL="http://localhost:$BE_PORT"
  export NEXT_PUBLIC_WS_URL="ws://localhost:$BE_PORT/api/agent/ws"
  export BACKEND_URL="http://localhost:$BE_PORT"
  if [ "$FE_MODE" = "dev" ]; then
    (cd "$FE_DIR" && exec npx next dev -p "$FE_PORT") > "$RUN_DIR/frontend.log" 2>&1 &
  else
    if [ ! -f "$FE_DIR/.next/BUILD_ID" ] || [ "$(cat "$RUN_DIR/built_for" 2>/dev/null)" != "$BE_PORT" ]; then
      echo "building frontend (about a minute)"
      (cd "$FE_DIR" && npx next build) > "$RUN_DIR/build.log" 2>&1 || { echo "build failed, see $RUN_DIR/build.log"; stop_all; exit 1; }
      echo "$BE_PORT" > "$RUN_DIR/built_for"
    fi
    (cd "$FE_DIR" && exec npx next start -p "$FE_PORT") > "$RUN_DIR/frontend.log" 2>&1 &
  fi
  echo $! > "$RUN_DIR/frontend.pid"

  wait_http "http://127.0.0.1:$BE_PORT/health" 60 || { echo "backend did not come up, see $RUN_DIR/backend.log"; stop_all; exit 1; }
  wait_http "http://localhost:$FE_PORT/login" 90 || { echo "frontend did not come up, see $RUN_DIR/frontend.log"; stop_all; exit 1; }

  echo "backend  http://localhost:$BE_PORT  (docs: /docs)  pid $(cat "$RUN_DIR/backend.pid")"
  echo "frontend http://localhost:$FE_PORT  pid $(cat "$RUN_DIR/frontend.pid")"
  echo "sign-in: the backend reads ADMIN_USERNAME / ADMIN_PASSWORD from its environment; if unset it uses the defaults hard-coded in Ecosystem-Forecast-Backend-main/app/routers/auth.py (see DEMO.md)"
  echo "stop with: $HERE/run.sh stop     logs in $RUN_DIR/"
}

case "${1:-start}" in
  start) start_all ;;
  stop) stop_all ;;
  status) status ;;
  restart) stop_all; start_all ;;
  *) echo "usage: $0 [start|stop|status|restart]"; exit 2 ;;
esac
