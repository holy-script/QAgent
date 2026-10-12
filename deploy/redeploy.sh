#!/bin/bash
# Deploys the current `main` to the live setup: pulls it into the Codespace backend, restarts it (so it runs with its secrets),
# makes the port public, then deploys the web app to Vercel. See CONTEXT.md.
#   deploy/redeploy.sh            both        deploy/redeploy.sh be     backend only        deploy/redeploy.sh fe     web only
# Needs: the GitHub CLI signed in (deploy/gh-login.sh) and the Vercel CLI signed in (`vercel login`, `vercel whoami`).
set -uo pipefail
WHAT="${1:-both}"
CODESPACE="${QAGENT_CODESPACE:-qagent-api-55gp5w4q7xwcvxq4}"
cd "$(git rev-parse --show-toplevel)"

gh_bin() { command -v gh >/dev/null 2>&1 && command -v gh || ls -d /tmp/ghcli/gh_*/bin/gh 2>/dev/null | head -1; }
GH="$(gh_bin)"; export GH_CONFIG_DIR="${GH_CONFIG_DIR:-/tmp/ghcli/config}"
state() { "$GH" codespace list --json name,state --jq ".[]|select(.name==\"$CODESPACE\")|.state"; }
wait_for() { for _ in $(seq 1 60); do [ "$(state)" = "$1" ] && return 0; sleep 10; done; echo "timed out waiting for $1"; return 1; }

if [ "$WHAT" = "be" ] || [ "$WHAT" = "both" ]; then
  [ -n "$GH" ] || { echo "no GitHub CLI: run deploy/gh-login.sh"; exit 1; }
  "$GH" auth status >/dev/null 2>&1 || { echo "GitHub CLI not signed in: run deploy/gh-login.sh"; exit 1; }
  git diff --quiet origin/main 2>/dev/null || echo "note: the Codespace pulls origin/main; push your commits first"
  echo "== backend: $CODESPACE ($(state))"
  if [ "$(state)" = "Shutdown" ]; then "$GH" api --method POST "user/codespaces/$CODESPACE/start" >/dev/null 2>&1; wait_for Available || exit 1; fi
  # The repo is private: give git a one-off token header for the pull (it is not stored anywhere).
  header=$(printf 'x-access-token:%s' "$("$GH" auth token)" | base64 | tr -d '\n')
  "$GH" codespace ssh -c "$CODESPACE" -- "cd /workspaces/QAgent && git -c http.extraheader='Authorization: Basic $header' pull -q origin main && git log --oneline -1"
  # Restart through stop/start so the lifecycle command runs WITH the Codespace secrets (an SSH shell would not have them).
  "$GH" codespace stop -c "$CODESPACE" >/dev/null 2>&1; wait_for Shutdown || exit 1
  "$GH" api --method POST "user/codespaces/$CODESPACE/start" >/dev/null 2>&1; wait_for Available || exit 1
  sleep 60
  "$GH" codespace ports visibility 8000:public -c "$CODESPACE"
  echo "health: $(curl -s -m 30 "https://$CODESPACE-8000.app.github.dev/api/health")"
fi

if [ "$WHAT" = "fe" ] || [ "$WHAT" = "both" ]; then
  echo "== web: Vercel"
  cd frontend
  vercel whoami >/dev/null 2>&1 || { echo "Vercel CLI not signed in: run 'vercel login'"; exit 1; }
  # First deploy only: vercel link --yes --project qagent-web ; printf '/api' | vercel env add NEXT_PUBLIC_API_URL production ;
  #                    printf 'https://<codespace>-8000.app.github.dev' | vercel env add BACKEND_URL production
  vercel --prod --yes > /tmp/vercel-deploy.out 2>&1 || vercel --prod --yes > /tmp/vercel-deploy.out 2>&1   # it sometimes fails once with "Not authorized"
  for _ in $(seq 1 30); do vercel ls 2>&1 | grep -q Building || break; sleep 8; done
  vercel ls 2>&1 | grep -E "Ready|Error" | head -1
  echo "live: https://qagent-web-mu.vercel.app"
fi
