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

- **Light mode is the default**, with a Light / Dark / Match-my-device switcher in the header (next-themes, choice remembered). Tokens live in `globals.css` (shadcn semantic names plus `brand`, `ok`, `warn`, `bad`, `violet` with soft tints) and every page reads them, so both themes are checked by the same code.
- **Component library**: shadcn/ui on Base UI (Nova preset: Geist, Lucide). Buttons, badges, tabs, tooltips, dropdown menu, sheets (step and proof panels), dialog (rewrite review), command palette (cmdk), toasts (sonner) are the library's components; `components/ui/index.tsx` keeps the app-specific pieces (status pills, metrics, empty and error states) on top of them.
- **Plain-language UX**: one vocabulary in `lib/terms.ts` and a Help page (`/help`). Playbook becomes test plan, flow becomes journey, finding becomes problem, issue becomes bug (Open / Fixed / Came back), mode becomes Smart / Thorough / Practice, Jev and Claude become fast AI and strong AI, "re-run from tape" becomes "Repeat exactly". Added: a four-step "How it works" on Home, a "Getting started" checklist on the Overview, a one-line explanation under each page title, "?" tooltips on jargon, friendlier empty states, and wording for every form field in the test plan editor.
- Checks: `tsc`, `eslint`, `next build` clean; `scripts/e2e_pages.py` 23/23 against the live stack in the new UI.

## Known gaps

- The "tape" timeline from the plan is not built (the journey strips and the decision loop stand in for it). The Steel/Plex design direction in the plan is superseded by the shadcn/ui decision.
- New pages show a "Needs the live API" notice in fixture mode; only the original pages have mock data.
- The playbook editor's add forms cover the common fields of each category (no inline editing of an existing item: remove and re-add, or use the raw view).
- Compare view still uses the original fixtures-era data shape.

## Next steps

1. **Review and land the branch**: merge `integration` into `main` (or push it for Coder 2 to continue from).
2. **Frontend polish** (Coder 2): decide on the design direction, build the tape timeline, mock data for the new pages, inline item editing, Compare on real runs.
3. **Backend gaps** (plan section 16): Claude planner, judged calls on the tape, per-flow reset and deterministic browser, upload retries and `artifact.uploaded`, Neon branch pin.
4. **Demo readiness**: rotate the shared Neon credentials, create the `qagent-artifacts` bucket (or keep `captures`), disable scale-to-zero, rehearse hybrid vs baseline (`make bench` numbers are in ASSUMPTIONS.md).
