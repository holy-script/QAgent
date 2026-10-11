# QAgent progress

Branches: `be` (backend, pushed), `fe` (frontend, pushed by Coder 2), `integration` (both merged, local). Details of every
task live in [DUAL_CODER_PLAN.md](DUAL_CODER_PLAN.md) section 15 (status per task) and section 16 (what exists vs the target).

## Where we are

| Track | Status |
|---|---|
| Backend B0-B21 | Done and tested (55 tests). Live run with real Jev, Claude, Neon Postgres and object storage: 8 findings, 8 issues, bug and run reports |
| Frontend F0-F5, F7 | Done on fixtures with a mock SSE replay (Coder 2) |
| Integration (F6) | **Started on `integration`**: the UI talks to the real API through `frontend/src/lib/api/adapter.ts`. Verified by driving the UI with a browser: app list, app page, playbooks, starting a run, live run page (flows, screenshots, graph, findings, network, logs), revisiting a finished run |

## How to run everything

```bash
make setup        # once: uv sync, npm install, Playwright browsers
make dev          # demo shop :8001, API :8000, frontend :3000 (frontend gets NEXT_PUBLIC_API_URL)
make dev-mock     # frontend only, on in-browser fixtures
make e2e          # drive the running stack through the UI, screenshots in /tmp/e2e
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

## Next steps

1. **Review the merge** and decide how `integration` lands: merge `be` + `fe` into `main`, or keep `integration` as the shared branch for F6.
2. **Close the F6 gaps** (backend data exists, UI does not show it yet):
   - candidate overlays and wait-frame strips on steps (`steps/{n}/candidates.json`, `wait/{n}.jpg`)
   - request/response bodies in the Network tab (`/network/{id}` and `/api/artifacts/.../response.json`)
   - decision `question`/`reasoning`, escalation reasons
3. **Pages for the new backend features** (F5, F7-F9 in the plan): issues list and issue page with the bug report, run report page
   with exports, traceability matrix, evidence drawer from a finding, playbook editor per category with live validation
   (`POST /playbooks/validate`), PRD extraction and normalize diff, replay with overrides.
4. **Types from the schema**: generate `frontend/src/lib/api/schema.d.ts` from `backend/openapi.json` (`npm run gen:api`) and
   retire the hand-written types where they overlap.
5. **Backend gaps** (plan section 16): Claude planner, judged calls on the tape, per-flow reset and deterministic browser,
   upload retries and `artifact.uploaded`, Neon branch pin.
6. **Demo readiness**: rotate the shared Neon credentials, create the `qagent-artifacts` bucket (or keep `captures`), disable
   scale-to-zero, rehearse hybrid vs baseline (`make bench` numbers are in ASSUMPTIONS.md).
