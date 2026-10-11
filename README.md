# QAgent

QAgent is an intelligent, high-speed automated QA agent that tests web applications end-to-end.

## Core Architecture
- **Fast Decision Layer**: TypeSafe AI Jev (`jev-1.13.0`) makes low-latency, cheap DOM action choices (~400ms).
- **Reasoning Layer**: Anthropic Claude Sonnet 4 via AWS Bedrock Converse (Bearer Token auth) for plan synthesis, recovery, and deep validation.
- **Execution Layer**: Playwright for Python executing actions inside an instrumented sandbox.
- **State & Graph**: LangGraph with SQLite checkpointing and streaming telemetry via Server-Sent Events (SSE).
- **Frontend Dashboard**: Next.js App Router with `@xyflow/react` visualizing execution flowcharts in real time.

## Quickstart
1. Review the architecture in [DUAL_CODER_PLAN.md](DUAL_CODER_PLAN.md) and current status in [PROGRESS.md](PROGRESS.md).
2. Put your keys in `backend/.env` (`JEV_API_TOKEN`, `BEDROCK_API_KEY`, database and `NEON_S3_*` storage settings).
3. One-time setup, including the pinned Chromium every machine uses: `make setup` (or `make browsers` alone).
4. Check the environment: `make doctor`.
5. Start everything: `make dev`, then open http://localhost:3000 and sign in.
6. Frontend only, no backend, on built-in demo data: `make dev-mock`.

## Sign-in
A single shared team account protects the API and the UI (HttpOnly cookie session, CORS limited to the frontend origin).
Set `AUTH_EMAIL`, `AUTH_PASSWORD` and `AUTH_SECRET` in `backend/.env`. For per-person accounts, see "Next steps" in PROGRESS.md.

## Browser
Runs use the pinned Playwright Chromium. Override with `QAGENT_BROWSER_PATH` (a Chromium executable) or `QAGENT_BROWSER_CHANNEL`; installed Chrome/Edge is a last resort with a warning. `backend/Dockerfile` bakes the same pinned build.

## Tests
| What | Command |
| --- | --- |
| Backend (pytest) | `make test` |
| Frontend types, lint, unit | `cd frontend && npm run typecheck && npm run lint && npm test` |
| Frontend end to end (every page in both themes, accessibility, key journeys, on demo data) | `cd frontend && npm run test:e2e` |
| All frontend checks | `cd frontend && npm run test:all` |

CI (`.github/workflows/ci.yml`) runs all of the above on every push and pull request.

## Deploying
`docker compose up -d --build` runs the web app, the API and Caddy on one machine behind one address. Steps: [deploy/README.md](deploy/README.md).

## Deleting data
Settings > Delete this app removes the app and everything it owns (plans, runs, bugs, reports) and its stored files. A single run can be deleted from its page.
