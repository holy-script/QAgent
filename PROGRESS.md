# QAgent progress

Branches: `be` (backend, pushed), `fe` (frontend, pushed by Coder 2), `integration` (both merged, local). Details of every
task live in [DUAL_CODER_PLAN.md](DUAL_CODER_PLAN.md) section 15 (status per task) and section 16 (what exists vs the target).

## Where we are

| Track | Status |
|---|---|
| Backend B0-B21 | Done and tested (55 tests). Live run with real Jev, Claude, Neon Postgres and object storage: 8 findings, 8 issues, bug and run reports |
| Frontend F0-F5, F7 | Done on fixtures with a mock SSE replay (Coder 2) |
| Integration F6 and the remaining frontend tasks | **Done on `integration`**: every backend feature has a page. `scripts/e2e_pages.py` drives 23 checks in a real browser against the live stack (all pass, no page errors, no failed API calls); `next build`, `tsc` and `eslint` are clean |

## How to run everything

```bash
make setup        # once: uv sync, npm install, Playwright browsers
make dev          # demo shop :8001, API :8000, frontend :3000 (frontend gets NEXT_PUBLIC_API_URL)
make dev-mock     # frontend only, on in-browser fixtures
make e2e          # drive the running stack through the UI, screenshots in /tmp/e2e
                  # (also: cd backend && uv run python ../scripts/e2e_pages.py for the 23 page checks)
make doctor       # preflight: Postgres, object storage, Jev, Bedrock, browser
make test         # 55 backend tests
```

## Integration work done on `integration`

- Merged `fe` into a new branch (no conflicts).
- Frontend adapter: backend DTOs and SSE events are translated into the shapes the UI already uses (apps, playbooks with
  versions and parsed flows, runs, flow history, step/decision/network/finding/span/log events). Check results are attached
  to the step they ran on, so the step drawer's "verified" list shows real checks.
- EventSource now registers a listener per backend event name (named SSE events never reach `onmessage`) and closes for
  good when the run report is ready.
- Backend changes found while integrating:
  - Playbook routes accept an app slug as well as an id; `POST /playbooks/{id}/versions` added.
  - Flow keys with `#` (edge-case variants) are URL-encoded in artifact URLs.
  - SSE now serves a live run from an in-memory event buffer and persists events in batches in the background: a stub run
    went from about 140 s to about 35 s against Neon, and a late viewer still gets the full history.
  - Artifact requests wait (up to about 30 s while the run is live) for an upload that has not landed yet, instead of
    redirecting to a storage URL that answers 404; uploads now run 4 at a time off the event loop.
  - New apps get their slug from the name (not the hostname).

## Frontend work done on `integration` (this round)

- **Step drawer**: before/after toggle, candidate overlays from `candidates.json`, wait frames, all from the new `GET /runs/{id}/artifacts`.
- **Network tab**: request and response bodies on demand (JSON is proxied by the API; presigned URLs cannot be fetched cross-origin).
- **Evidence panel** from any finding: annotated/before/after screenshots, check inputs with the source of each value and a link to the recorded call, wait frames, decisions, integrity line.
- **Issues**: list with status filter, issue page with the full bug report, occurrence list, Copy as issue, MD/HTML/PDF export. Issue count in the tab bar; open issues and requirement coverage on the Overview.
- **Run report** page (summary, flows, requirement coverage, findings by category, performance, grounded recommendations, test-quality notes, exports, regenerate) and a **View report** button on the run page.
- **Traceability** matrix: requirement, priority, status, covering items with their latest result, linked issues.
- **Playbook editor**: one tab per category with counts, add forms per category, existing items with remove, live validation (errors block Save), coverage panel, raw Markdown view in sync, **Extract from the PRD** (proposals with verbatim quotes, accepted one by one), **Normalize with Claude** with a line diff to review. PRD field added to Settings.
- **Re-run from tape** with gate overrides and live fallback; **command palette** (Ctrl/Cmd+K) for pages, runs and issues.
- Types for the new pages come from the generated schema (`npm run gen:api` reads `backend/openapi.json`).
- Backend additions: `GET /runs/{id}/artifacts`, textual artifacts proxied instead of redirected, items and links in `POST /playbooks/validate`.

## UI refresh (branch `ui-refresh`, on top of `integration`)

- **Light mode is the default**, with a Light / Dark / Match-my-device switcher in the header (own provider, choice remembered, no flash). Tokens live in `globals.css` (shadcn semantic names plus `brand`, `ok`, `warn`, `bad`, `violet` with soft tints) and every page reads them, so both themes are checked by the same code.
- **Component library**: shadcn/ui on Base UI (Nova preset: Geist, Lucide). Buttons, badges, tabs, tooltips, dropdown menu, sheets (step and proof panels), dialog (rewrite review), command palette (cmdk), toasts (sonner) are the library's components; `components/ui/index.tsx` keeps the app-specific pieces (status pills, metrics, empty and error states) on top of them.
- **Plain-language UX**: one vocabulary in `lib/terms.ts` and a Help page (`/help`). Playbook becomes test plan, flow becomes journey, finding becomes problem, issue becomes bug (Open / Fixed / Came back), mode becomes Smart / Thorough / Practice, Jev and Claude become fast AI and strong AI, "re-run from tape" becomes "Repeat exactly". Added: a four-step "How it works" on Home, a "Getting started" checklist on the Overview, a one-line explanation under each page title, "?" tooltips on jargon, friendlier empty states, and wording for every form field in the test plan editor.
- Checks: `tsc`, `eslint`, `next build` clean; `scripts/e2e_pages.py` 23/23 against the live stack in the new UI.

- **Brand colours**: gold primary and blue secondary scales in light mode, a navy surface with lifted tints in dark mode (all text pairs pass WCAG AA, enforced by the e2e accessibility checks).
- **Auth**: shared team account (`admin@chryselys.com`), HMAC-signed HttpOnly cookie, login throttle, every API route protected, CORS limited to the frontend. Sign-in screen, session gate and sign-out in the UI.
- **Standard browser**: pinned Playwright Chromium first (`make browsers`), explicit overrides, installed Chrome only as a warned fallback; Dockerfile for a reproducible environment.
- **Deleting**: app and run deletion cascade through the database and object storage; confirmation dialogs (type the app name for an app).
- **Reliability**: orphaned runs are marked failed on restart; uploads retry with backoff and emit `artifact.uploaded`.
- **Editor**: CodeMirror 6 with Markdown highlighting, item IDs and bindings coloured, problems underlined on their line, edit-in-place for existing items (unseen fields are preserved).
- **Tests and demo data**: every page and feature has demo data (in-browser fixtures with a scripted live run). Backend 91 pytest tests, frontend 43 unit tests, 63 Playwright tests (all pages x both themes, accessibility, phone width, auth, key journeys). CI runs all of them.
- **Done**: credential rotation (not needed, closed), `qagent-artifacts` bucket created and configured.

- **Tape and cost**: judge verdicts and report calls are recorded as `model_calls` (new table, migration `b7e2c4a91d30`), so "Repeat exactly" answers judgements and reports from the recording with no model calls. Judge, planner and report cost roll into the run total with a breakdown; `GET /runs/{id}/tape` lists every call and the run page has an **AI calls** tab.
- **Planner (opt-in)**: "Let the strong AI plan each journey first" has Claude write a short note per step that becomes a hint for the step decisions. Steps are never rewritten; plans are on the tape.
- **Determinism**: the browser clock is fixed (`FIXED_CLOCK_ISO`), animations are off, locale and timezone are pinned, and each journey resets its own server-side state (demo shop: `POST /__reset?scope=session`) so parallel journeys never disturb each other. `DETERMINISTIC_BROWSER=false` turns this off.
- **API**: app-scoped routes only for creating and listing (`/apps/{id}/runs`, `/apps/{id}/playbooks`); lookups by id stay flat (`/runs/{id}`, `/issues/{id}`).
- **Retention (per app)**: each app sets how long its finished runs are kept (Settings > Keeping old runs: delete after N days, always keep the newest M). Applied hourly and on demand ("Clean up now"); rows and stored files go together; running runs are never touched. Migration `c3d9e5f1a2b4`.
- **File uploads**: a step can attach a file to a page's file field. Each app has its own test files (Settings > Test files, up to 10 MB each) plus built-in samples (png, pdf, txt, csv, json). Which file a step uses: the journey's `file:` test data, a name in the step text, or one matching the field's accepted types. Hidden "drop zone" inputs work. The demo shop has a profile page with an avatar upload and a planted bug (accepts any file type); `playbooks/uploads.md` tests it. Migration `d4a1b8c6e7f2`.
- **Dashboard and layout**: the home page opens with a dashboard (runs, clean-run rate, open bugs, AI cost, runs per day, bugs by severity, app health, latest runs, worst bugs; 7/30/90 days) from `GET /dashboard`. App pages use a side list on wide screens (tabs on phones), wider content area, and two-column Settings. The demo data now has 10 runs over 24 days (the oldest three clean).
- **Guided tours** (driver.js): home, an app, a run, a test plan and a bug each have a tour; the Tour button in the header starts the one for the current page, first-time visitors get the home tour and a one-time offer on other pages, `?tour=home` starts one from a link. Steps for parts not on screen (phone) are skipped.
- **Richer UI**: the blue secondary now carries the header, app side panel, card headers, hero banners and chart series (gold stays for actions). Dashboard has stat cards with sparklines, hover/keyboard charts (runs per day, AI cost area, clean-run gauge), severity bars and a "what to do next" card.
- **Hugging Face Spaces**: single-container image and publish script in `deploy/hf/`, steps in `deploy/HUGGINGFACE.md` (not built here: no Docker daemon).
- **Codespaces backend**: `.devcontainer/` + `deploy/codespaces/` run the API and demo shop in a Codespace (`deploy/CODESPACES.md`); verified locally with Docker, not in a real Codespace.
- **Deploy**: `docker-compose.yml` + `deploy/` run Caddy, the web app and the backend (one worker) on one machine behind one address. See `deploy/README.md`. Not yet exercised on a real VM.

## Known gaps

- Auth is one shared account by choice; no per-person identity, audit trail or roles.
- Run events are held in memory, so the backend must run as a single worker.
- The planner is opt-in and has only been exercised with a stubbed model in tests; try it live once before relying on it.

## Next steps

1. **Push and review** `ui-refresh`, then merge into `integration` / `main`.
2. ~~Apply the migrations~~ done on the dev Neon database (`model_calls`, app retention). Repeat `make migrate` on any other database.
3. **First deployment**: see `deploy/README.md` (one VM) or `deploy/DEMO.md` (Vercel + FastAPI Cloud notes, demo runbook). On a VM with `docker compose up -d --build` (the images have not been built in this environment).
4. **Demo readiness**: turn off Neon scale-to-zero (paid plan) or warm the database first, point `DATABASE_URL` at a dedicated "demo" branch, rehearse Smart vs Thorough with `make bench`.
