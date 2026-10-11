# QAgent Implementation Progress

## Overall Status
- **Current Phase**: Parallel execution across Phase 2 (Backend foundation) & Phase 3 (Browser layer)
- **Frontend**: Initialized with Next.js 16 (App Router, TypeScript, Tailwind CSS, `@xyflow/react`, `lucide-react`)
- **Parallel Work Plan**: See [TRACKS.md](file:///Users/holyscript/Desktop/projects/QAgent/TRACKS.md) (Backend Feature Flow vs Frontend UX Flow) and [DUAL_CODER_PLAN.md](file:///Users/holyscript/Desktop/projects/QAgent/DUAL_CODER_PLAN.md)

---

## Phases & Breakdown

### [x] Phase 1 — Root scaffold (~10 min)
- [x] **1a.** Create monorepo structure (dirs: `backend/`, `frontend/`, `.gitignore`, `.env.example`)
- [x] **1b.** Write `Makefile` with `setup`, `doctor`, `dev`, `test`, `bench` targets
- [x] **1c.** Write `ASSUMPTIONS.md` + `README.md` skeleton

---

### [ ] Phase 2 — Backend foundation (~20 min)
- [x] **2a.** `uv init backend/`, `pyproject.toml` with all dependencies configured (`qagent` package)
- [ ] **2b.** `.env.example` with all variables & sync local environment
- [ ] **2c.** `backend/qagent/decision/` — Pydantic models + `DecisionModel` Protocol
- [ ] **2d.** `JevDecider` (`httpx` async, retry with backoff, semaphore concurrency, latency timing, tape recording)
- [ ] **2e.** `StubDecider` + `RecordingDecider` + `ReplayDecider`

---

### [ ] Phase 3 — Browser layer (~20 min)
- [ ] **3a.** `sandbox.py` — Playwright context, frozen clock, viewport
- [ ] **3b.** `extractor.py` — compact state dict + candidate action list (≤40 IDs)
- [ ] **3c.** `executor.py` — resolve ID → locator, screenshot, network capture

---

### [ ] Phase 4 — LangGraph engine (~20 min)
- [ ] **4a.** State graph: `plan` → `observe` → `decide` → `gate` → `act` → `verify` → (`loop` | `finish` | `escalate`) → `report`
- [ ] **4b.** SQLite checkpointer, step/time budgets, cancel flag
- [ ] **4c.** Telemetry: `asyncio` event bus → SSE

---

### [ ] Phase 5 — FastAPI + SSE (~10 min)
- [ ] **5a.** `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/events`, `POST /runs/{id}/stop`
- [ ] **5b.** `GET /health` (Jev + Bedrock reachability checks)

---

### [ ] Phase 6 — Demo shop (~15 min)
- [ ] **6a.** FastAPI + Jinja: `/products`, `/cart`, `/checkout`
- [ ] **6b.** 4 bugs (toggled via env/query param)
- [ ] **6c.** `POST /__reset`, seeded RNG

---

### [ ] Phase 7 — Playbook + formulas (~10 min)
- [ ] **7a.** `checkout-flow.yaml`
- [ ] **7b.** Pydantic validator
- [ ] **7c.** Empty formula module with safe-eval TODO

---

### [ ] Phase 8 — ClaudeDecider (~15 min)
- [ ] **8a.** `httpx` Bearer-token client to Bedrock Converse
- [ ] **8b.** Forced tool-use for structured JSON output
- [ ] **8c.** Wire into engine with baseline mode toggle

---

### [ ] Phase 9 — Frontend (~25 min)
- [x] **9a.** Next.js (App Router, TS, Tailwind) — initialized + installed `@xyflow/react`, `lucide-react`, verified build passes
- [ ] **9b.** `/runs/new` — form with URL, playbook selector, mode toggle
- [ ] **9c.** `/runs/[id]` — SSE consumer, step timeline, screenshot pane, metrics strip, React Flow decision graph
- [ ] **9d.** `/runs/[id]/replay`, `/compare` — empty stubs

---

### [ ] Phase 10 — Tests + bench (~15 min)
- [ ] **10a.** pytest: `JevDecider` (fixture+retry), gate logic, extractor, playbook
- [ ] **10b.** `make bench` script: p50/p95 Jev latency, cost/step, accuracy at 10/20/40 candidates

---

## Coder 2 — Frontend (`fe` branch)
Runs on fixtures with no backend; set `NEXT_PUBLIC_API_URL` to switch to the real API. `npm run gen:api` regenerates types from the OpenAPI schema once B0 lands (hand-written stand-ins live in `frontend/src/lib/api/types.ts`).

- [x] **F0** Tailwind tokens, typed API client (`lib/api/`), app shell, TanStack Query
- [x] **F1** Home, `/apps/new`, app layout (tabs + live-run banner), Overview with run launcher
- [x] **F2** Playbooks list, upload, review screen (inline parse errors, edit → new version, history, confirm)
- [x] **F3** Run page: flow rows with screenshot strips, `@xyflow/react` Graph tab, step drawer; pause/speed/replay on the mock SSE stream
- [x] **F4** Network, Trace, Logs, Findings tabs
- [x] **F5** Runs history, Flows + flow history, Settings
- [ ] **F6** Real API switch — client paths are guessed in `lib/api/client.ts`; reconcile with B0/B7 (event envelope, route names)
- [x] **F7** Compare view (two finished runs, per-metric bars)
- [ ] **F8** Replay tape editor / normalize diff (P2)

Deep link: `/apps/<slug>/runs/<id>?tab=graph&step=checkout:3`.
