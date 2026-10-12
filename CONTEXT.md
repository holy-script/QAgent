# QAgent: context for a new chat

Paste or reference this file at the start of a new conversation. It records what the project is, how it is built, where it is
deployed, how to operate it, and what we learned the hard way. Secrets are NOT in this file (see "Secrets" for where they live).

## What it is
QAgent is an autonomous QA tool for web apps. A user adds an app, describes what to test in a **test plan** (journeys, requirements,
expected outcomes), and QAgent drives a real Chromium through it, decides each action with AI, checks results, and produces bugs
with proof (screenshots, server calls, steps to reproduce) and reports.

- **Fast AI**: Jev (TypeSafe System One API, `jev-1.13.0`) picks which page element performs a step (about 300 ms, cheap).
- **Strong AI**: Claude on AWS Bedrock Converse (forced tool use) for escalations, judged checks, planning, reports, and for
  *goal-driven journeys* (the "director" that chooses each next step from the live page).
- **Execution**: Playwright (Python) in a sandbox; **orchestration**: LangGraph per journey; **storage**: Neon Postgres + Neon S3.
- Repo: `github.com/holy-script/QAgent`, branch **`main`** is the deployed branch (all work merged; `ui-refresh` is stale).

## Repository map
```
backend/qagent/
  api/            FastAPI app (main.py), auth.py (shared-account cookie), routes/ (apps, runs, playbooks, issues, reports,
                  dashboard, text, observability, traceability, artifacts, health, dev), sse.py, mappers.py, seed.py
  engine/         graph.py (the LangGraph engine: plan -> begin_step -> observe -> decide -> gate -> escalate -> act -> settle ->
                  verify -> finish), secrets.py (SecretMasker), findings.py, callbacks.py
  decision/       jev.py, claude.py (BedrockClient), stub.py, tape.py, ledger.py (TapedJudge/LedgerClient: model calls on the tape),
                  planner.py (per-step notes), director.py (goal journeys), fewshot.py
  browser/        sandbox.py (context, fixed clock, trace/HAR, storage_state), extractor.py (candidate elements with unique
                  data-qagent-id stamps), executor.py (acts on exactly one element, reads typed text back), launcher.py (pinned
                  Chromium), uploads.py (file-upload steps), wait_frames.py, network_recorder.py
  checks/ playbooks/ reports/ runs/manager.py (RunManager: start/replay/recover) storage/ (db, objects, upload_queue, purge,
  retention, vault, persistence_sink) domain/ (models, schemas, runspec, events)
  migrations/versions/   Alembic (head: e5b2d7a9c3f1 app_credentials)
frontend/src/        Next.js 16 App Router (cacheComponents), shadcn/ui on Base UI, Tailwind v4, TanStack Query
  app/(app)/...      pages are `page.tsx` wrappers (AuthGate + `export const instant = false`) around client `view.tsx`
  components/        ui/ (kit), dashboard/, run/, live/ (editors), guide.tsx, tour.tsx (driver.js), dictation.tsx, ...
  lib/api/           client.ts (api object: real or MOCK), live.ts (hooks), adapter.ts, mock-live.ts, fixtures.ts, schema.d.ts (generated)
  lib/               guide.ts, tours.ts, dictation.ts, playbook-md.ts + playbook-validate.ts (TS mirror of the Python parser)
frontend/e2e/        Playwright suite on a production build in demo mode
demo-shop/           the sample target app (FastAPI + Jinja): 6 planted bugs, /login (admin / s3cret-pass), /profile avatar upload
playbooks/           checkout.md (the seed plan), uploads.md
deploy/              redeploy.sh + gh-login.sh (live deploy), HUGGINGFACE.md, CODESPACES.md, DEMO.md, README.md (VM), hf/, codespaces/, ci.github-actions.yml
.devcontainer/       Codespaces dev container (Chromium image + sshd)
PROGRESS.md          status + feature list (kept current); DUAL_CODER_PLAN.md = original architecture; CONTEXT.md = this file
```

## Core concepts
- **Test plan** = Markdown with sections: Requirements (REQ-n), Formulas (F-n), UX rules (UX-n), Gotchas (G-n), Edge cases (EC-n),
  Flows, Reasoning examples. A flow has `#### Steps` (exact steps) **or** `#### Goal` (high level; the director chooses the steps),
  `#### Expect`, `#### Test data`. Flow field `- role: setup` marks the **sign-in journey**: it runs first, alone, and every other
  journey starts from its signed-in session (cookies + local storage) and runs one at a time.
- **Modes**: Smart (`hybrid`: Jev, Claude when unsure), Thorough (`baseline`: Claude), Practice (`stub`: no AI; cannot run goal journeys).
- **Tape / Repeat exactly**: every decision, judge, planner, director and report call is recorded (`decisions`, `model_calls`);
  a replay answers from the recording, makes no model calls, and costs nothing (strict for the director).
- **Sign-in details** (Settings): encrypted per-app credentials (`app_credentials`, Fernet key from `CREDENTIALS_KEY` or
  `AUTH_SECRET`). Steps like "Enter the username/password" are filled from them; the AI sees names only; every recorded place is
  masked `[hidden]`. A plan's own test-data value wins (edge cases); `<fill in>` placeholders fail the step clearly.
- **After each step** the engine records what the page shows (URL changed, sign-in form still visible, alerts); a failed sign-in
  stops the journey ("sign-in failed: ... says: ...") with a finding; other failures include that note.
- **Per-app**: retention policy (clean-up), test files for upload steps, sign-in details, delete app / plan / run.
- **Dashboard** on Home (`GET /dashboard`), **Setup guide** (7 steps, per app, localStorage + data-driven), **tours**, **dictation**
  (browser speech recognition + `POST /text/refine`), **plan from the PRD** (`POST /apps/{id}/prd/plan`).
- **Demo mode**: `NEXT_PUBLIC_API_URL` unset => the frontend runs on in-browser fixtures (10 demo runs). `NEXT_PUBLIC_REQUIRE_LOGIN=true`
  emulates sign-in there. The e2e suite uses this.

## Deployment (live)
```
browser -> Vercel (web, /api rewrite) -> GitHub Codespace (API + Chromium + demo shop) -> Neon (Postgres + S3)
```
- **Web**: https://qagent-web-mu.vercel.app (Vercel project `qagent-web`, team `palashs-projects-279ee569`, deployed with the CLI from
  `frontend/`). Env: `NEXT_PUBLIC_API_URL=/api`, `BACKEND_URL=https://qagent-api-55gp5w4q7xwcvxq4-8000.app.github.dev`
  (read at BUILD time: a new backend address needs a redeploy). `frontend/vercel.json` sets `npm ci --legacy-peer-deps`.
- **Backend**: Codespace `qagent-api-55gp5w4q7xwcvxq4` (2-core, 4 h idle timeout, repo `holy-script/QAgent`, branch main). It stops when idle;
  the URL stays the same for the same Codespace. `.devcontainer` runs `deploy/codespaces/start.sh` on every start
  (uv sync, demo shop :8001, `alembic upgrade head`, API :8000). Port 8000 must be **Public** (set via `gh codespace ports visibility`
  or, if the secret `GH_PAT` exists, automatically by start.sh).
- **Alternatives written up**: `deploy/HUGGINGFACE.md` (backend-only Docker Space, image tested locally), `deploy/README.md` (one VM,
  docker compose + Caddy).
- **Secrets** live in: `backend/.env` (local, git-ignored), GitHub **Codespaces user secrets** (same names, no quotes; `AUTH_SECRET` is
  separate from local), Vercel env vars. Names: `DATABASE_URL`, `DATABASE_URL_DIRECT`, `NEON_S3_*`, `TYPESAFE_*`, `JEV_*`, `BEDROCK_*`,
  `AUTH_SECRET`, optional `CREDENTIALS_KEY`, `AUTH_EMAIL`/`AUTH_PASSWORD`. The team login is the one from `backend/qagent/config.py`
  defaults unless overridden. Never commit secrets; `.env` files are ignored.

### How to deploy (backend + web) and how the CLIs are signed in
Two scripts do everything; they were verified end to end:
```
deploy/gh-login.sh          # once per machine: gets a throw-away GitHub CLI and signs it in (device flow)
deploy/redeploy.sh          # both:   pull main into the Codespace, restart it with its secrets, port public, health check, then Vercel
deploy/redeploy.sh be       # backend only
deploy/redeploy.sh fe       # web only
```
**GitHub CLI (backend side).** `gh` is not installed system-wide (Homebrew fails when the Xcode licence is unaccepted). `deploy/gh-login.sh`
downloads the official binary from the GitHub releases page into `/tmp/ghcli` and signs in with the device flow
(`gh auth login -w -s codespace,repo`): it prints a one-time code (also copied to the clipboard); open https://github.com/login/device,
enter it, approve. Config lives in `/tmp/ghcli/config` (`export GH_CONFIG_DIR=/tmp/ghcli/config`); /tmp is cleared on reboot, so rerun the
script then. Scopes: `codespace` (start/stop/ports/create) and `repo` (read the private repo). Revoke any time at
github.com/settings/applications. Everything `redeploy.sh` does for the backend, by hand:
1. `git push origin main`; if there is a new migration also `cd backend && uv run alembic upgrade head` (shared Neon DB).
2. Start the Codespace if it is `Shutdown`: `gh api --method POST user/codespaces/<name>/start`; wait for `Available`.
3. Pull into it. The repo is private, so pass a one-off token header:
   `gh codespace ssh -c <name> -- "cd /workspaces/QAgent && git -c http.extraheader='Authorization: Basic $(printf 'x-access-token:%s' "$(gh auth token)" | base64)' pull origin main"`
4. Restart it with **`gh codespace stop -c <name>`, wait for `Shutdown`, then start again** (never just re-run `start.sh` from the SSH shell: that
   shell has no Codespace secrets and the API would quietly use local SQLite). Wait about 60 s.
5. `gh codespace ports visibility 8000:public -c <name>` (a restart can reset it; automatic if the Codespace secret `GH_PAT` exists).
6. Check `https://<name>-8000.app.github.dev/api/health`: postgres, storage, Jev and Bedrock must all be `true`.
To create a fresh Codespace instead: `gh codespace create -R holy-script/QAgent -b main -m basicLinux32gb --idle-timeout 240m --default-permissions`
(user secrets are attached automatically if they allow the repo; secrets were set with `gh secret set NAME --user --repos holy-script/QAgent`,
values piped on stdin). A new Codespace has a new address: update the Vercel env `BACKEND_URL` and redeploy the web app.

**Vercel CLI (web side).** `vercel` IS installed and signed in as `holy-script` (`vercel whoami`; sign in again with `vercel login`).
The folder `frontend/.vercel/` (git-ignored) links the project `qagent-web`. By hand: `cd frontend && vercel --prod --yes` (retry once if it says
"Not authorized"), then `vercel ls` until `Ready`. First-time setup, only if the project is ever recreated:
`vercel link --yes --project qagent-web`, `printf '/api' | vercel env add NEXT_PUBLIC_API_URL production`,
`printf 'https://<name>-8000.app.github.dev' | vercel env add BACKEND_URL production`. Env vars are read at build time, so change them, then redeploy.

**Smoke test after a deploy:** sign in through https://qagent-web-mu.vercel.app (or `POST /api/auth/login` with a cookie jar), `GET /api/apps`,
open a run page (screenshots must load), and optionally run a Practice-mode run on the Demo Shop.

## Commands
```
make setup | dev | dev-mock | doctor | test      (macOS note: `make` fails if the Xcode licence is not accepted; run the commands directly)
cd backend && uv sync --all-extras --all-groups && uv run pytest -q            # 114 tests (~90 s); uses SQLite files + a local demo shop
cd backend && uv run alembic upgrade head                                       # Neon
cd backend && uv run python -c "import json;from qagent.api.main import app;json.dump(app.openapi(),open('openapi.json','w'),indent=2)"
cd frontend && npm run gen:api                                                  # regenerate src/lib/api/schema.d.ts from openapi.json
cd frontend && npx tsc --noEmit && npx eslint src e2e && npx vitest run         # 51 unit tests
cd frontend && npx playwright test --project=setup --project=signed-out --project=app   # 80 e2e tests, builds + serves on :3100
```
After changing an API route or schema: regenerate openapi.json, then `npm run gen:api`.

## Gotchas and lessons (save yourself the time)
- **macOS `sed -i` needs a backup arg**; chained `sed -i ... && ...` silently skipped edits. Use Python for file edits.
- **`.gitignore` had `runs/`**, which hid `backend/qagent/runs/` (the run manager) from git. It is `/runs/` now; check `git status --ignored`
  when "it works locally but not in the Codespace".
- **Selectors**: pages often give two inputs the same selector (`input.w-full`). The extractor stamps every candidate with a unique
  `data-qagent-id`, and the executor must act on exactly one element (never "the first match").
- **Docker `--env-file` keeps quotes** around values; strip them. Codespaces/HF secrets are pasted without quotes.
- **Cookies across sites do not work reliably**, so the web app proxies `/api/*` to the backend (Next rewrite via `BACKEND_URL`);
  asset URLs from the backend start with `/api/...` and must not be prefixed with the `/api` base twice (`API_ORIGIN`).
- **Hydration**: components that read `localStorage`/browser APIs must use `useSyncExternalStore` with a server snapshot (theme, dictation
  support, guide memory). `useParams/usePathname/useSearchParams` need a Suspense boundary under cacheComponents.
- **driver.js** (tours/guide) turns off pointer events for everything except the highlighted element: dropdown portals needed CSS
  overrides (globals.css). The guide pointer must be destroyed on unmount and must not dismiss itself for "results".
- **React Query + mock mode**: the mock `updateApp` mutates the same object, so memo deps on `app` do not change; depend on primitives.
- **Playwright e2e**: inject fake speech recognition as a plain-JS string (compiler helpers break `addInitScript` functions) and replace
  both `SpeechRecognition` and `webkitSpeechRecognition`; use `fill()` (not `type()`) in the CodeMirror editor (it auto-continues lists).
- **Per-flow determinism**: fixed clock + no animations + `POST /__reset?scope=session` through the flow's own browser session.
- **Neon free plan** sleeps after ~5 min idle; the first query is slower, nothing breaks.
- Several features were verified against the real services only in part: real-microphone dictation, a live goal-driven run (tested with
  scripted answers), the Hugging Face and VM deployments (Docker-tested / documented), an actual multi-minute AI rewrite through the
  Vercel proxy.

## Known gaps / ideas
- Auth is one shared account (by choice). No per-user identity, audit trail or roles.
- Live run events are in memory => the API must run as ONE worker.
- Codespaces stops when idle (no cron keep-alive was set up on purpose; the guide is in `deploy/CODESPACES.md`).
- Product document import accepts only `.md` / `.txt` (no PDF/Word).
- A failed sign-in is reported both as a sign-in finding and as the 401 network finding.
- CI workflow is saved as `deploy/ci.github-actions.yml`; add it as `.github/workflows/ci.yml` through GitHub's web editor (the push
  credential lacked the `workflow` scope).
- Possible next work: run goal-driven journeys live against a real app and tune the director prompt; per-user accounts; PDF import;
  background jobs for very long AI rewrites; a "needs AI" warning in the run launcher when a plan has goal journeys and Practice mode is chosen.

## Conventions
- Plain-language UI (see `frontend/src/lib/terms.ts`): playbook -> test plan, flow -> journey, finding -> problem, issue -> bug,
  Jev/Claude -> fast AI/strong AI, "re-run from tape" -> "Repeat exactly".
- Brand: gold primary `#C9922A` (actions), deep-blue secondary `#1A4F72` (surfaces, header, charts). Light default, dark supported;
  accessibility (axe, WCAG AA) is enforced by the e2e suite on every page in both themes.
- Every new feature gets: backend tests, TS unit tests where logic exists, e2e journeys on demo data, and a PROGRESS.md entry.
- Commit messages end with the `Co-Authored-By` line; do not merge or push anything the user has not asked for.
