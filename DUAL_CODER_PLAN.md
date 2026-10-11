# QAgent Dual-Coder Build & Architecture Plan

QAgent tests web apps. You register an App (a URL), attach Markdown playbooks, and run them. Claude (on AWS Bedrock) plans and judges. Jev (TypeSafe AI) makes fast, repeated decisions inside each run. Playwright drives the browser. Every run records screenshots, API traffic, logs, and traces, and every model call is recorded on a tape so runs can be replayed deterministically.

**Team Division**:
- **Coder 1 (be branch)**: Owns backend (`backend/`, `demo-shop/`). Focuses on agent features, decision engines, database persistence, Playwright runtime, and APIs.
- **Coder 2 (fe branch)**: Owns frontend (`frontend/`). Focuses on UX-first design, interactive decision flowcharts (`@xyflow/react`), real-time SSE telemetry, and run analytics.

**Priorities**: P0 = required for the demo. P1 = strongly wanted. P2 = only if time allows.

---

## 1. Security & Configuration
- Secrets live exclusively in `backend/.env` (gitignored). `.env.example` contains variable names and placeholders, never credentials.
- Never log secrets, connection strings, or full request headers.
- The Neon storage keys are deliberately named `NEON_S3_*` (not `AWS_*`) so boto3 does not confuse them with Bedrock credentials.

### Environment Variables Schema
```bash
# --- Neon Postgres ---
# Pooled URL (host contains "-pooler"): used by the app.
DATABASE_URL="postgresql+psycopg://USER:PASSWORD@ep-...-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
# Direct URL (same host without "-pooler"): used by Alembic migrations and the LangGraph checkpointer.
DATABASE_URL_DIRECT="postgresql+psycopg://USER:PASSWORD@ep-....c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- Neon Object Storage (S3-compatible) ---
NEON_S3_ENDPOINT="https://br-....storage.c-4.ap-southeast-1.aws.neon.tech"
NEON_S3_ACCESS_KEY_ID="nak_..."
NEON_S3_SECRET_ACCESS_KEY="nsk_..."
NEON_S3_REGION="ap-southeast-1"
NEON_S3_BUCKET="qagent-artifacts"

# --- Jev (TypeSafe AI) ---
TYPESAFE_API_KEY=""
TYPESAFE_BASE_URL="https://api.typesafe.ai"
JEV_MODEL="jev-1.13.0"            # pin a version; confirm in preflight
JEV_MAX_CONCURRENCY="4"

# --- Claude on Bedrock ---
BEDROCK_REGION=""                 # region where Sonnet 4.6 is available
BEDROCK_API_KEY=""                # Bedrock API key (Bearer token)
BEDROCK_REASONING_MODEL_ID=""     # exact Sonnet 4.6 model or inference-profile ID

# --- Gating ---
GATE_AUTO_MIN="0.75"
GATE_ESCALATE_MIN="0.45"

# --- Runtime ---
QAGENT_ALLOWED_HOSTS="localhost,127.0.0.1"
FLOW_STEP_BUDGET="25"
FLOW_TIME_BUDGET_S="90"
FLOW_MAX_PARALLEL="3"
NETWORK_BODY_CAP_KB="256"

# Frontend needs only NEXT_PUBLIC_API_URL
```

---

## 2. Architecture & The Three Clean Boundaries

```
Frontend (Next.js 16)
   │  REST + SSE
FastAPI  ── RunManager ── LangGraph engine ── Decision layer (Jev | Claude | Stub, wrapped by Recording/Replay)
   │                         │               └─ Browser layer (Playwright: sandbox, extractor, executor, recorders)
   │                         └─ emits events
   │                              │
   │                    Persistence sink ──> Neon Postgres (rows, event log, spans, logs, tape)
   │                    Upload queue    ──> Neon Object Storage (screenshots, DOM, traces, HAR, bodies)
   └─ reads Postgres; serves presigned artifact URLs
```

1. **The engine never touches the database or storage**: It receives a `RunSpec`, a sandbox, a decider, and an `EventSink`. It only emits events and hands files to the upload queue.
2. **Persistence is a subscriber**: The persistence sink writes events, steps, decisions, findings, network calls, spans, and logs. SSE reads from the same event log.
3. **Every model call passes through the decision interface**: Recording and replay wrap any decider, so determinism comes from the tape, not the models.

### Role Split
- **Claude**: Planning, escalated judgment, normalizing freeform playbooks, report text. A few expensive calls per run.
- **Jev**: Bounded, repeated decisions (next action, step success, risk). Generates no text.
- **Deterministic Code**: Extraction, execution, verification, formulas. Formulas are evaluated as code (`simpleeval`), never by an LLM.

---

## 3. Technology Stack

| Area | Choice |
|---|---|
| **Backend** | Python 3.11+, `uv`, FastAPI, `sse-starlette`, Pydantic v2, SQLModel on SQLAlchemy 2 (async), `psycopg` 3 (`psycopg[binary,pool]`), Alembic |
| **Agent** | LangGraph + `langgraph-checkpoint-postgres` |
| **Browser** | Playwright for Python (Chromium) |
| **Models** | Jev via `httpx` (TypeSafe API); Claude Sonnet 4.6 via Bedrock Converse API with Bearer API key |
| **Storage** | Neon Postgres; Neon Object Storage via `boto3` (explicit endpoint, path-style addressing) |
| **Observability** | OpenTelemetry SDK (spans in Postgres), `structlog` (JSON logs) |
| **Playbooks** | `markdown-it-py` (parsing), `simpleeval` (formulas) |
| **Frontend** | Next.js 16 (App Router, TypeScript), Tailwind, `@xyflow/react`, `openapi-typescript`, TanStack Query |
| **Tests** | pytest, respx (HTTP mocking), Playwright against static HTML fixtures |

### Neon-Specific Settings
- **Pooled engine**: Pass `connect_args={"prepare_threshold": None}` so psycopg avoids prepared statements that fail under PgBouncer transaction pooling.
- **Direct connection**: Used for Alembic migrations and the LangGraph `PostgresSaver` in its own `langgraph` schema.
- **No LISTEN/NOTIFY**: Pooler does not support it; the event bus stays in-process, and SSE streams from persisted events.
- **S3 client**: `boto3.client("s3", endpoint_url=NEON_S3_ENDPOINT, region_name=NEON_S3_REGION, aws_access_key_id=..., aws_secret_access_key=..., config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))`.

---

## 4. Repository Layout

```
qagent/
  Makefile  README.md  ASSUMPTIONS.md  DUAL_CODER_PLAN.md  PROGRESS.md  TRACKS.md
  playbooks/                    checkout-flow.md
  demo-shop/                    FastAPI + Jinja, port 8001
  backend/
    pyproject.toml  alembic.ini  .env.example
    migrations/
    qagent/
      config.py                 settings (pydantic-settings)
      domain/                   models.py (tables), schemas.py (DTOs), runspec.py, events.py
      decision/                 base.py, jev.py, claude.py, stub.py, tape.py
      browser/                  types.py, sandbox.py, extractor.py, executor.py, network_recorder.py, wait_frames.py
      engine/                   graph.py, state.py, gating.py, verify.py, findings.py, tracing.py
      playbooks/                parser.py, formulas.py, validate.py, versioning.py, normalize.py
      storage/                  db.py, repo.py, objects.py, upload_queue.py, persistence_sink.py
      runs/                     manager.py
      api/                      main.py, sse.py, routes/{apps,playbooks,flows,runs,network,artifacts,observability,health,dev}.py
      cli.py                    python -m qagent.cli run --app <slug> --mode stub|hybrid|baseline
    fixtures/                   run_events.jsonl, sample pages, recorded Jev responses
    tests/
  frontend/
    src/app/  src/components/  src/lib/api/ (generated types + client)
```

---

## 5. Data Model & Object Storage

### Postgres Tables (All IDs are UUIDs, all timestamps timestamptz, flexible fields jsonb)
- **`apps`**: `id`, `slug`, `name`, `base_url`, `allowed_hosts[]`, `description`, `prd_markdown`, `default_mode`, `gate_overrides`, `redact_keys[]`, `created_at`
- **`playbooks`**: `id`, `app_id`, `name`, `current_version_id`, `status` (`draft`, `confirmed`)
- **`playbook_versions`**: `id`, `playbook_id`, `version_no`, `raw_markdown`, `parsed` (jsonb), `warnings` (jsonb), `content_hash`, `created_at`
- **`runs`**: `id`, `app_id`, `playbook_version_id`, `mode`, `trigger` (`manual`, `replay`), `replay_of_run_id`, `status`, `started_at`, `finished_at`, `totals` (jsonb)
- **`flow_runs`**: `id`, `run_id`, `flow_key`, `status`, `step_count`, `duration_ms`, `failure_reason`
- **`steps`**: `id`, `flow_run_id`, `seq`, `intent`, `action_id`, `action_label`, `page_tag`, `url`, `status`, `artifacts_complete`
- **`step_timings`**: `step_id`, `observe_ms`, `extract_ms`, `decide_ms`, `gate_ms`, `act_ms`, `settle_ms`, `verify_ms`
- **`decisions`**: `id`, `step_id`, `decider`, `model_version`, `question`, `choice`, `probabilities` (jsonb), `confidence`, `branch`, `latency_ms`, `input_tokens`, `output_tokens`, `input_hash`, `request` (jsonb), `response` (jsonb)
- **`findings`**: `id`, `flow_run_id`, `step_seq`, `severity`, `kind` (`formula`, `dom`, `network`, `timing`), `title`, `expected`, `actual`, `evidence` (jsonb)
- **`network_calls`**: `id`, `flow_run_id`, `step_seq`, `method`, `url`, `status`, `duration_ms`, `req_size`, `resp_size`, `is_api`, `req_artifact_id`, `resp_artifact_id`
- **`artifacts`**: `id`, `run_id`, `flow_run_id`, `step_seq`, `kind`, `object_key`, `content_type`, `size_bytes`, `sha256`, `uploaded_at`
- **`spans`**: `trace_id`, `span_id`, `parent_span_id`, `run_id`, `name`, `kind`, `start_ns`, `end_ns`, `attributes` (jsonb), `status`
- **`log_entries`**: `id`, `run_id`, `flow_run_id`, `step_seq`, `level`, `source`, `message`, `data` (jsonb), `ts`
- **`events`**: `run_id`, `seq`, `type`, `payload` (jsonb), `ts`. Primary key `(run_id, seq)`. Append-only.

### S3 Key Layout (`qagent-artifacts`)
```
apps/{app_id}/runs/{run_id}/flows/{flow_key}/
  trace.zip  har.json  console.jsonl
  steps/{seq}/screenshot.jpg  dom.html  a11y.json  candidates.json
  steps/{seq}/wait/{n}.jpg
  network/{call_id}/request.json  response.json
```

---

## 6. Markdown Playbooks & Demo Shop (5 Bugs)

### Sample Playbook Format (`playbooks/checkout-flow.md`)
```markdown
# Playbook: Checkout flow
base_url: http://localhost:8001

## Flow: add-to-cart
Severity: high

### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart

### Expect
- Cart shows 2 items
- Total is visible

### Test data
- qty: 2
- coupon: EXPIRED10

### Formulas
- cart_total: `total == round(sum(i.price * i.qty for i in items) * (1 + tax_rate), 2)`
  - source: both
  - bindings: items=api:/api/cart.items, total=ui:[data-testid=cart-total], tax_rate=const:0.08

### Edge cases
- Quantity set to 0
- Apply expired coupon
```

### Demo Shop 5 Bugs Matrix
| Bug # | Simulated Defect | Caught By |
|---|---|---|
| **1** | Cart badge count disagrees with cart contents | DOM check (UI vs API) |
| **2** | Missing postal-code validation | Edge-case flow + DOM check |
| **3** | Every 3rd payment request returns 500 (counter cleared by `/___reset`) | Network check |
| **4** | Infinite spinner after applying coupon | Settle timeout + wait frames |
| **5** | Tax applied before discount, yielding wrong total | Formula check (`simpleeval`) |

---

## 7. Parallel Dual-Coder Task Breakdown

### 👨‍💻 Coder 1: Backend Flow (`be` branch)
| Code | Pri | Task | Done When |
|---|---|---|---|
| **B0** | P0 | Domain schemas, `types.py`, `base.py`, event models, fixture routes, `/dev/sse-replay`, export OpenAPI schema | Coder 2 can generate types & replay recorded run |
| **B1** | P0 | Neon configuration, dual engines, Alembic migrations, `objects.py`, upload queue | `make migrate` passes; upload tests pass |
| **B2** | P0 | Decision layer: `JevDecider` (retry 429/529, semaphore, model-version capture), `Stub`, `Recording`, `Replay` | Unit tests pass against recorded tape |
| **B3** | P0 | Playbooks: `markdown-it-py` parser, formula validation (`simpleeval`), versioning, `playbooks/checkout-flow.md` | Parser & formula tests pass |
| **B4** | P0 | Browser: Sandbox (trace, HAR, console), DOM extractor (≤40 candidates), executor, network recorder, wait frames | Extractor test on static HTML passes |
| **B5** | P0 | Engine: LangGraph graph, gating, budgets, checkpointer, spans, structlog, persistence sink | `qagent.cli run --mode stub` writes rows & artifacts |
| **B6** | P0 | Verify + findings: DOM, network status, formula, and timing checks (>2s) | Bugs 1, 3, and 5 produce findings |
| **B7** | P0 | Real API routes: RunManager, SSE with resume, network/spans/logs/artifact routes | Run started from API streams and resumes |
| **B8** | P0 | Demo shop with 5 bugs and `POST /__reset` | Toggling bugs alters test findings |
| **B9** | P1 | `ClaudeDecider` (forced tool use) + planner + escalation; `/normalize` endpoint | Baseline mode completes checkout |
| **B10** | P1 | `make bench`: p50/p95 latency, cost/step, candidate scaling (10, 20, 40) | Benchmark figures recorded in `ASSUMPTIONS.md` |
| **B11** | P2 | Replay endpoint with overrides; Neon branch "Pin for demo" | Replay verification complete |

### 👩‍💻 Coder 2: Frontend UX Flow (`fe` branch)
| Code | Pri | Task | Done When |
|---|---|---|---|
| **F0** | P0 | Next.js 16 setup, Tailwind tokens, generated API client, app shell | Typed client builds |
| **F1** | P0 | Home page, `/apps/new`, app layout with tabs & live banner, Overview | App creation working against stubs |
| **F2** | P0 | Playbooks list, upload, Markdown review screen with inline errors, version history | Uploading sample shows parsed flows |
| **F3** | P0 | Run page against `/dev/sse-replay`: flow rows with screenshot strips, Graph tab (`@xyflow/react`), step drawer | Recorded run plays back smoothly |
| **F4** | P0 | Network, Trace, Logs, and Findings tabs | Each tab renders fixture data |
| **F5** | P1 | Runs history table, Flows tab, flow history page, Settings | Complete navigation & history views |
| **F6** | P0 | Switch to real API; handle error and empty states | Real run visible end-to-end |
| **F7** | P1 | Compare view (Hybrid vs Baseline on one playbook version) | Comparison metrics render |
| **F8** | P2 | Replay tape editor; normalize diff view | Tape viewer operational |

---

## 8. Sync Points & Git Workflow

```mermaid
gitGraph
    commit id: "scaffold (main)"
    branch be
    branch fe
    checkout be
    commit id: "B0: Contracts & Fixtures"
    checkout fe
    commit id: "F0: API Client & Tokens"
    commit id: "F1-F4: UI & Replay Tab"
    checkout be
    commit id: "B1-B5: DB, Engine & Demo"
    checkout main
    merge be id: "Sync 1: Engine Proven"
    checkout fe
    merge main id: "Sync 2: Switch to Real API"
    commit id: "F6: End-to-End Live"
    checkout main
    merge fe id: "Sync 3: Demo Ready"
```

1. **Contracts Frozen (after B0 + F0)**: Frontend builds against generated types and fixture routes. Changes to `domain/` require agreement.
2. **Engine Proven (after B1–B5 + B8)**: CLI run in stub mode passes against the demo shop, with rows in Neon and artifacts in S3.
3. **Live UI (after B6–B7 + F3–F4)**: Frontend switches from `/dev/sse-replay` to real API runs.
4. **Demo Ready (after B9–B10 + F5–F7)**: Hybrid and baseline runs complete with pitch benchmark numbers.
