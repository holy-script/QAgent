# QAgent Dual-Coder Parallel Execution Plan

This plan organizes the 10 project phases into two parallel tracks (**Track A: Agent Core & Decision Engine** and **Track B: Runtime, API, Environment & Frontend**). 

The division ensures minimal merge conflicts, clear interface contracts, and continuous independent progress.

---

## Developer Allocation & Ownership

| Track | Primary Focus | Tech Stack | Root Dirs |
|---|---|---|---|
| **Coder 1 (Track A: Core & Reasoning)** | Decision engine, Bedrock integration, LangGraph agent loops, playbooks, benchmarks | Python, LangGraph, Pydantic, HTTPX, SQLite | `backend/qagent/decision/`<br>`backend/qagent/engine/`<br>`backend/qagent/playbooks/`<br>`backend/tests/` |
| **Coder 2 (Track B: Runtime & Experience)** | Browser automation sandbox, FastAPI + SSE streaming, Demo test shop, Next.js frontend | Python, Playwright, FastAPI, Next.js 16, React Flow (`@xyflow/react`), Tailwind | `backend/qagent/browser/`<br>`backend/qagent/api/`<br>`demo-shop/`<br>`frontend/` |

---

## Contract Interfaces (Zero-Conflict Boundary)

To allow both coders to work independently from minute 1:
1. **Decision Protocol (`qagent.decision.base`)**: Coder 1 defines the Pydantic schemas (`CandidateAction`, `DecisionResult`, `DecisionModel`).
2. **Action Dict / Locator Schema**: Coder 2's extractor produces `list[CandidateAction]` (IDs 1-40 with element tags, coordinates, text); Coder 1 consumes it.
3. **SSE Event Schema**: Defined upfront in `qagent.engine.events` (`RUN_STARTED`, `STEP_OBSERVED`, `DECISION_MADE`, `ACTION_EXECUTED`, `RUN_FINISHED`, `ERROR`).
4. **FastAPI Route Spec**:
   - `POST /runs` `{ target_url, playbook, mode }` -> `{ run_id }`
   - `GET /runs/{id}` -> Run state
   - `GET /runs/{id}/events` -> SSE event stream
   - `POST /runs/{id}/stop` -> Halts run

---

## Parallel Execution Timeline

```mermaid
gantt
    title QAgent Parallel Dual-Coder Roadmap
    dateFormat  X
    axisFormat %s min

    section Coder 1 (Track A: Core)
    Phase 2c-2e: Decision Layer (Jev, Stub, Recorders) :active, a1, 0, 20
    Phase 4a-4b: LangGraph Engine & Checkpointer        :a2, 20, 40
    Phase 7: Playbooks & YAML validator                :a3, 40, 50
    Phase 8: ClaudeDecider (Bedrock Converse tool-use)  :a4, 50, 65
    Phase 10: Pytest suites & Benchmarking script       :a5, 65, 80

    section Coder 2 (Track B: Platform & UI)
    Phase 3: Browser Sandbox, Extractor & Executor      :active, b1, 0, 20
    Phase 5: FastAPI Engine runner + SSE endpoint       :b2, 20, 30
    Phase 6: Demo Shop (4 bug toggles + reset)          :b3, 30, 45
    Phase 9b-9c: Frontend (/runs/new, SSE pane, graph)  :b4, 45, 70
    Integration & End-to-End Verification               :b5, 70, 80
```

---

## Phase Matrix & Assignees

| Phase | Description | Owner | Output Artifacts |
|---|---|---|---|
| **Phase 1** | Root monorepo scaffold | Completed | `Makefile`, `README.md`, `ASSUMPTIONS.md` |
| **Phase 2** | Backend foundation & Decision models | **Coder 1** | `qagent/decision/{base,jev,tape,stub}.py` |
| **Phase 3** | Playwright sandbox, DOM state extractor & action executor | **Coder 2** | `qagent/browser/{sandbox,extractor,executor}.py` |
| **Phase 4** | LangGraph engine, SQLite checkpointer, state transitions | **Coder 1** | `qagent/engine/{graph,state,checkpointer,events}.py` |
| **Phase 5** | FastAPI app, run lifecycle & SSE telemetry endpoints | **Coder 2** | `qagent/api/{main,routes,deps}.py` |
| **Phase 6** | Demo shop webapp with 4 togglable bugs (`DEMO_BUGS=1,2,3,4`) | **Coder 2** | `demo-shop/{main.py,templates/,products.json}` |
| **Phase 7** | Playbook schema, `checkout-flow.yaml` & validator | **Coder 1** | `qagent/playbooks/{schema.py,checkout-flow.yaml}` |
| **Phase 8** | ClaudeDecider (Bedrock Bearer Token Converse + forced tool use) | **Coder 1** | `qagent/decision/claude.py` |
| **Phase 9** | Next.js 16 App Router UI (`/runs/new`, `/runs/[id]`, React Flow) | **Coder 2** | `frontend/src/app/runs/` |
| **Phase 10** | Pytest unit/integration tests & benchmarking suite | **Coder 1** (supported by Coder 2) | `backend/tests/`, `qagent/bench.py` |

---

## Detailed Task Breakdown

### 👨‍💻 Coder 1 Tasks (Track A)
1. **Decision Protocol & Jev Client (`qagent/decision/`)**:
   - `models.py`: `CandidateAction`, `DecisionResult`, `ConfidenceTier` (`AUTO`, `ESCALATE`, `STOP`).
   - `jev.py`: `JevDecider` using async `httpx` targeting `https://api.typesafe.ai/v1/systemone` with exponential backoff on 429/529, semaphore concurrency limit, tape recording.
   - `stubs.py`: `StubDecider`, `RecordingDecider`, `ReplayDecider` for hermetic offline tests.
2. **LangGraph Engine (`qagent/engine/`)**:
   - Nodes: `observe` → `decide` → `gate` → `act` → `verify` → (`loop` | `escalate` | `finish`).
   - SQLite checkpointer for resumability and audit trail.
   - Time budget & step budget guards.
3. **Claude Reasoning Decider (`qagent/decision/claude.py`)**:
   - Async Bearer token call to Bedrock Converse endpoint (`us.anthropic.claude-sonnet-4-20250514-v1:0`).
   - Forced tool-use pattern enforcing structured JSON output for complex recoveries.
4. **Playbooks & Benchmarks (`qagent/playbooks/` & `qagent/bench.py`)**:
   - YAML schema for multi-step goals & validations.
   - Benchmark script measuring p50/p95 latency and cost across 10, 20, and 40 candidate DOM elements.

---

### 👩‍💻 Coder 2 Tasks (Track B)
1. **Playwright Browser Sandbox (`qagent/browser/`)**:
   - `sandbox.py`: Headless/headed context, viewport standard (1280x800), clock freezing/network throttling options.
   - `extractor.py`: Traverses DOM to extract actionable elements (buttons, inputs, links, selects), assign numeric IDs 1-40, and create state JSON with bounding boxes.
   - `executor.py`: Maps selected ID back to Playwright locator, executes click/fill/press, captures step screenshot and network logs.
2. **FastAPI Server & Telemetry (`qagent/api/`)**:
   - Mounts SSE broadcast channel from engine's `asyncio` event bus.
   - Endpoints: `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/events`, `POST /runs/{id}/stop`, `GET /health`.
3. **Demo Shop (`demo-shop/`)**:
   - Standalone FastAPI + Jinja2 app on port 8001.
   - Product list, cart session, multi-step checkout form.
   - 4 simulated QA bugs toggled via environment variables or query params:
     - Bug 1: Cart count mismatch.
     - Bug 2: Missing postal code validation / disabled submit.
     - Bug 3: Intermittent payment gateway 500.
     - Bug 4: Infinite spinner on coupon application.
   - `POST /__reset` endpoint for automated clean-state test runs.
4. **Frontend UI (`frontend/`)**:
   - `/runs/new`: Interactive run launcher with target URL, playbook selector, and decision mode (Jev-Only, Claude-Baseline, Dual-Gated).
   - `/runs/[id]`: Live dashboard with SSE stream subscriber, execution step timeline, screenshot pane, confidence gauge, and `@xyflow/react` decision node visualizer.

---

## Synchronization Checkpoints
- **Sync Point 1 (Minute 20)**:
  - Coder 1 exports `DecisionModel` & `CandidateAction`.
  - Coder 2 verifies `extractor.py` yields valid `list[CandidateAction]` into `StubDecider`.
- **Sync Point 2 (Minute 45)**:
  - Coder 1's LangGraph engine connects to Coder 2's `sandbox.py` and publishes events to `FastAPI` SSE.
  - Coder 2 tests `demo-shop` against a basic run.
- **Sync Point 3 (Minute 70)**:
  - Frontend connects live to `GET /runs/{id}/events` rendering real-time execution steps and screenshots.
