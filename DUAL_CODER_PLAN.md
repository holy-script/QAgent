# QAgent build plan

QAgent tests web apps. You register an App (a URL), attach Markdown playbooks, and run them. Claude (on AWS Bedrock) plans, judges, and writes reports. Jev (TypeSafe AI) makes the fast, repeated decisions inside each run. Playwright drives the browser. Every run records screenshots, API traffic, logs, and traces. Every finding links back to the requirement it violates and to the evidence that proves it.

**Team**: Coder 1 owns the backend (`backend/`, `demo-shop/`, `be` branch). Coder 2 owns the frontend (`frontend/`, `fe` branch).

**Priorities**: P0 = required for the demo. P1 = strongly wanted. P2 = only if time allows.

> **Status key** used in this document: ✅ built and tested · 🟡 partly built · ⬜ not started. Section 16 lists exactly what exists today versus what this plan describes.

---

## 1. Security and configuration (do first)

- Rotate the Neon database password and the Neon storage key. The current values were shared in a chat.
- Secrets live only in `backend/.env` (gitignored). `.env.example` contains names and placeholders, never values.
- Never log secrets, connection strings, or full request headers.

### Environment variables

The Neon storage keys are deliberately not named `AWS_*`. boto3 reads `AWS_*` variables automatically, so the Bedrock client would otherwise pick up the Neon keys.

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
NEON_S3_BUCKET="qagent-artifacts"   # the dev project currently uses an existing bucket named "captures"

# --- Jev (TypeSafe AI) ---
TYPESAFE_API_KEY=""
TYPESAFE_BASE_URL="https://api.typesafe.ai"
JEV_MODEL="jev-1.13.0"            # pin the concrete version; GET /v1/models lists aliases (jev-latest, jev-preview) that currently resolve to it
JEV_MAX_CONCURRENCY="4"

# --- Claude on Bedrock ---
BEDROCK_REGION=""                 # pick a region where Sonnet 4.6 is available (see preflight)
BEDROCK_API_KEY=""                # Bedrock API key (Bearer token)
BEDROCK_REASONING_MODEL_ID=""     # exact Sonnet 4.6 model or inference-profile ID, looked up in preflight

# --- Gating ---
GATE_AUTO_MIN="0.75"
GATE_ESCALATE_MIN="0.45"

# --- Runtime ---
QAGENT_ALLOWED_HOSTS="localhost,127.0.0.1"
QAGENT_INJECT_TRACEPARENT="true"  # add a W3C traceparent header to requests to allowlisted hosts
QAGENT_BROWSER_CHANNEL=""         # empty = bundled Chromium, falling back to installed Chrome; or "chrome"
FLOW_STEP_BUDGET="25"
FLOW_TIME_BUDGET_S="90"
FLOW_MAX_PARALLEL="3"
NETWORK_BODY_CAP_KB="256"
STEP_SLA_MS="2000"
SETTLE_TIMEOUT_MS="3000"
```

The frontend needs only `NEXT_PUBLIC_API_URL`.

---

## 2. Architecture

```
Frontend (Next.js 16)
   |  REST + SSE
FastAPI ─ RunManager ─ LangGraph engine ─ Decision layer (Jev | Claude | Stub, wrapped by Recording/Replay)
   |                       |             ├ Browser layer (Playwright: sandbox, extractor, executor, recorders)
   |                       |             └ Checks (formulas, UX rules, expectations, edge cases)
   |                       └ emits events
   |                            |
   |                  Persistence sink ──> Neon Postgres (rows, event log, spans, logs, tape, evidence links)
   |                  Upload queue    ──> Neon Object Storage (screenshots, DOM, traces, HAR, bodies, reports)
   |
   └ Report engine (after each run): findings → issues (dedupe) → bug reports + recommendation report
```

### Boundaries that keep the code clean

1. **The engine never touches the database or storage.** It receives a `RunSpec` (app config, pinned playbook version, flows, mode, thresholds), a sandbox, a decider, and an `EventSink`. It only emits events and hands artifacts to the upload queue.
2. **Persistence is a subscriber.** The persistence sink writes events, steps, decisions, findings, network calls, spans, logs, and evidence links. SSE reads from the same event log.
3. **Every model call passes through the decision interface.** Recording and replay wrap any decider, so determinism comes from the tape, not from the models.
4. **Reports are assembled from stored facts.** The report engine reads only from Postgres and object storage. Claude writes prose on top of those facts and can only cite evidence IDs that exist (section 10).

### Role split

- **Claude**: planning, escalated judgment, judged UX checks, PRD requirement extraction, normalizing freeform playbooks, report narrative and recommendations.
- **Jev**: bounded, repeated decisions (next action, step success, risk) and cheap yes/no checks on page text. Generates no text.
- **Deterministic code**: extraction, execution, verification, formulas, rule-based UX checks, steps-to-reproduce, evidence assembly, deduplication. Formulas are evaluated as code, never by an LLM.

---

## 3. Stack

| Area | Choice |
|---|---|
| Backend | Python 3.11+, `uv`, FastAPI, `sse-starlette`, Pydantic v2, SQLModel on SQLAlchemy 2 (async), psycopg 3 (`psycopg[binary,pool]`), Alembic |
| Agent | **LangGraph** `StateGraph` + `langgraph-checkpoint-postgres` (`AsyncPostgresSaver`); **langchain-core** runnables wrap every model call and a callback handler turns graph/model runs into spans |
| Browser | Playwright for Python (Chromium); axe-core injected for accessibility checks (P1) |
| Models | Jev via `httpx` (TypeSafe System One API); Claude Sonnet 4.6 via the Bedrock Converse API with a Bearer API key |
| Storage | Neon Postgres; Neon Object Storage via `boto3` (explicit endpoint, path-style addressing) |
| Observability | Spans stored in Postgres (OTel-shaped ids and ns timestamps), `structlog` (JSON logs) |
| Playbooks | `markdown-it-py` (parsing), `simpleeval` (formulas) |
| Reports | Jinja2 templates → Markdown and HTML; PDF by printing the HTML with Playwright `page.pdf()` (no extra dependency); Pillow for annotated screenshots |
| Frontend | Next.js 16 (App Router, TypeScript), Tailwind v4, shadcn/ui on Base UI (fully restyled), `@xyflow/react`, TanStack Query, Table and Virtual, `openapi-typescript`. Full library list and design rules in section 13. |
| Tests | pytest, respx (HTTP mocking), Playwright against the live demo shop and static HTML fixtures |

### Neon-specific settings

- **Pooled engine**: pass `connect_args={"prepare_threshold": None}` so psycopg doesn't use server-side prepared statements, which break under PgBouncer transaction pooling.
- **Direct connection**: used for Alembic and for the LangGraph `AsyncPostgresSaver` (in its own `langgraph` schema, set via `search_path`; session state like this does not survive the pooler).
- **Scale-to-zero**: disable it on the compute for demo day, so the first query doesn't pay a cold start.
- **No LISTEN/NOTIFY**: it doesn't work through the pooler. The event bus stays in-process.
- **S3 client**: `boto3.client("s3", endpoint_url=NEON_S3_ENDPOINT, region_name=NEON_S3_REGION, aws_access_key_id=..., aws_secret_access_key=..., config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))`. Credentials are passed explicitly, never from the environment chain.
- **Integer widths**: epoch nanoseconds need `BIGINT` (a migration widened `spans.start_ns/end_ns`).

---

## 4. Repository layout

```
qagent/
  Makefile  README.md  ASSUMPTIONS.md  DUAL_CODER_PLAN.md
  backend/
    pyproject.toml  alembic.ini  .env.example
    migrations/
    qagent/
      config.py                 settings (pydantic-settings), one place for all env vars
      domain/                   models.py (tables), schemas.py (API DTOs), runspec.py, events.py
      decision/                 base.py, jev.py, claude.py, stub.py, tape.py
      browser/                  types.py, sandbox.py, extractor.py, executor.py,
                                network_recorder.py, wait_frames.py, traceparent.py
      engine/                   graph.py, state.py, gating.py, tracing.py, callbacks.py,
                                findings.py, verify.py
      checks/                   expectations.py, formulas.py, ux_rules.py, ux_judged.py,
                                edge_cases.py, timing.py
      playbooks/                parser.py, schema.py, validate.py, versioning.py,
                                normalize.py, prd_extract.py, coverage.py, formulas.py
      reports/                  findings.py, issues.py (dedupe), repro.py (steps to reproduce),
                                evidence.py, annotate.py, bug_report.py, run_report.py,
                                grounding.py, templates/
      storage/                  db.py, repo.py, objects.py, upload_queue.py, persistence_sink.py,
                                checkpoint.py
      runs/                     manager.py
      api/                      main.py, sse.py, deps.py, mappers.py, seed.py,
                                routes/{apps,playbooks,flows,runs,network,artifacts,
                                observability,issues,reports,traceability,health,dev}.py
      bench.py                  python -m qagent.bench  (make bench)
      cli.py                    python -m qagent.cli run --app <slug> --mode stub|hybrid|baseline
    fixtures/                   run_events.jsonl, sample pages, recorded Jev responses
    tests/
  demo-shop/                    FastAPI + Jinja, port 8001
  playbooks/                    checkout.md
  frontend/
    src/app/  src/components/  src/lib/api/ (generated types + client)
```

---

## 5. Playbook structure

A playbook is one Markdown file split into seven categories. Every item has a stable ID, and items reference each other by ID. Those IDs are what make findings traceable back to the PRD.

| Category | ID prefix | What it holds | Used by |
|---|---|---|---|
| Requirements | `REQ-` | Testable statements from the PRD, each with acceptance criteria and a PRD reference | Coverage check, findings, reports |
| Flows | `flow_key` | User journeys: steps, expectations, test data, and which requirements and checks they cover | Planner (Claude), navigation (Jev), verifier |
| Formulas | `F-` | Calculations to verify in code, with bindings to UI and API values | Verifier (code only) |
| UX rules | `UX-` | Consistency and usability rules: some checked by code, some judged | Verifier (code), Jev (cheap yes/no), Claude (judged) |
| Gotchas | `G-` | Known traps in this app (async updates, flaky widgets, misleading labels), optionally with machine hints | Planner, settle logic, verifier, judge |
| Edge cases | `EC-` | Unusual inputs or states with the expected behavior | Become extra flow variants; verifier |
| Reasoning examples | `RX-` | Few-shot examples teaching Claude how to handle tricky situations: scenario, context and challenge, step-by-step strategy | Claude only (planner, escalation, judge, report) |

### Example

```markdown
# Playbook: Checkout
base_url: http://localhost:8001
prd: PRD-checkout-v2

## Requirements
### REQ-1: Cart total applies the discount before tax
- prd_ref: §3.2 Pricing
- acceptance: total = (subtotal − discount) × (1 + tax_rate), rounded to 2 decimals
- priority: high

### REQ-2: Quantity must be at least 1
- prd_ref: §2.4 Cart
- acceptance: Quantity 0 removes the item or shows an error. No $0 line items.

### REQ-3: Checkout requires a valid postal code
- prd_ref: §4.1 Address form
- acceptance: Submitting without a postal code shows an inline error and blocks submission.

## Formulas
### F-1: cart_total
- rule: `total == round((subtotal - discount) * (1 + tax_rate), 2)`
- source: both
- bindings: subtotal=api:/api/cart.subtotal, discount=api:/api/cart.discount, total=ui:[data-testid=cart-total], tax_rate=const:0.08
- tolerance: 0.01
- verifies: REQ-1

## UX rules
### UX-1: Cart count is consistent across the app
- check: consistent_value
- targets: ui:[data-testid=cart-badge], api:/api/cart.count
- severity: medium

### UX-2: No loading state lasts longer than 3 seconds
- check: max_wait
- max_ms: 3000
- severity: high

### UX-3: Form errors are visible and explain the problem
- check: judged
- question: Is an error message visible next to the invalid field that says what is wrong?
- severity: medium

### UX-4: Prices use the same currency format everywhere
- check: format
- targets: ui:[data-testid$=price], ui:[data-testid=cart-total]
- pattern: ^\$\d{1,3}(,\d{3})*\.\d{2}$
- severity: low

## Gotchas
### G-1: The cart badge updates only after /api/cart responds
- wait_for: api:/api/cart
- note: Reading the badge before the response arrives gives a stale count, which is not a bug.

### G-2: The coupon field trims whitespace on blur, not on submit
- note: Type the coupon, then press Tab before clicking Apply.

## Edge cases
### EC-1: Quantity set to 0
- applies_to: add-to-cart
- expect: The item is removed or an error appears. No $0 line item.
- covers: REQ-2
- test_data: qty=0

### EC-2: Expired coupon
- applies_to: apply-coupon
- expect: An error says the coupon has expired. The total doesn't change.
- test_data: coupon=EXPIRED10

### EC-3: Missing postal code
- applies_to: checkout
- expect: An inline error appears and the order is not submitted.
- covers: REQ-3
- checks: UX-3

## Flows
### Flow: add-to-cart
- covers: REQ-1, REQ-2
- checks: F-1, UX-1, UX-4
- severity: high

#### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart

#### Expect
- Cart shows 2 items
- Total is visible

#### Test data
- qty: 2

## Reasoning examples
### RX-1: Telling a slow API apart from a broken one
- scope: escalation, judge
- context: A spinner is visible and the expected element hasn't appeared. It could be slow, failed silently, or stuck.
- strategy:
  1. Check the network log for the request the step triggered.
  2. If it's still pending, wait until the time budget runs out, then report a timing finding, not a functional one.
  3. If it returned 4xx or 5xx, report a network finding and cite that call.
  4. If it returned 200 but the UI didn't update, report a UI-state finding and cite both the response and the screenshot.
```

### How each category is used at run time

- **Requirements** are never executed directly. Flows, formulas, and edge cases point to them with `covers:` or `verifies:`. The review screen flags any requirement that nothing covers.
- **Formulas** are evaluated in code during the verify step of every flow that lists them under `checks:`.
- **UX rules** come in two kinds:
  - *Rule-based (P0)*: `consistent_value` (a UI value equals another UI or API value), `format` (regex), `max_wait` (no spinner or settle longer than N ms), `no_console_errors`, and `a11y` (axe-core, P1). Checked in code.
  - *Judged (P1)*: `check: judged` with a yes/no question. Jev answers it first as a `noul` question over the page-text summary. If its confidence falls in the escalation band, Claude answers it from the before and after screenshots. Judged findings are labeled as judged in reports and capped at medium severity unless a code check also fails.
- **Gotchas**:
  - Their `note` is added to the Claude planner and judge prompts.
  - Machine hints are applied in code: `wait_for: api:<path>` makes the settle step wait for that response, and `ignore_console: <pattern>` suppresses a known console error.
  - They are never sent to Jev in full. Only a one-line hint goes into the state, when it applies to the current page.
- **Edge cases** expand into flow variants. EC-1 on `add-to-cart` runs as `add-to-cart#EC-1` with its own test data and its `expect` added as an extra check. Variants get their own history.
- **Reasoning examples** go into Claude's system prompt as few-shot examples for the scopes they list. At most 3 are included per call, chosen by keyword overlap with the current flow and step. The IDs and content hashes of the included examples are recorded on the tape, so replay stays deterministic.

### Parsing and validation

- `markdown-it-py` builds a syntax tree, and `##` headings map to categories. No LLM is involved in the normal path.
- **Binding sources**: `api:<path>.<json.path>` reads the endpoint's live (or recorded) response. `ui:<selector>` reads `textContent` from the DOM. `const:<value>` is a literal. Selectors appear only in playbooks and check code, never in anything sent to Jev.
- **Validation rules** (errors block confirmation; warnings don't):
  - Error: an ID is duplicated, or an ID is referenced but doesn't exist.
  - Error: a formula doesn't compile under `simpleeval` (whitelist: `sum`, `round`, `abs`, `min`, `max`, `len`; generator expressions allowed), or one of its variables has no binding.
  - Error: a UX rule has an unknown check type or is missing a required field.
  - Warning: a requirement isn't covered by any flow, formula, or edge case.
  - Warning: a flow was renamed since the last version (its history will split).
  - Warning: an unknown section or field.
- **PRD extraction (P1)**: Claude reads the app's PRD and proposes `## Requirements` items with `prd_ref`s. The user reviews and accepts them one by one.
- **Normalize (P1)**: for freeform Markdown, Claude rewrites the document into this format. The UI shows a diff, and the user must confirm before a version is created.

### Editing in the UI

The Markdown file stays the source of truth. The playbook editor shows one tab per category, and each tab has an "Add" card with form fields, in the style of the reasoning-example form (scenario, context, strategy). Saving a card writes that item back into the Markdown, and the user can switch to the raw Markdown view at any time. Each confirm creates a new version.

---

## 6. Data model (Neon Postgres)

All IDs are UUIDs, all timestamps are `timestamptz`, and flexible fields are `jsonb`.

### Apps and playbooks

| Table | Key fields |
|---|---|
| `apps` | `id`, `slug`, `name`, `base_url`, `allowed_hosts[]`, `description`, `prd_markdown`, `default_mode`, `gate_overrides`, `redact_keys[]`, `created_at` |
| `playbooks` | `id`, `app_id`, `name`, `current_version_id`, `status` (`draft`, `confirmed`) |
| `playbook_versions` | `id`, `playbook_id`, `version_no`, `raw_markdown`, `parsed` (jsonb), `warnings` (jsonb), `content_hash`, `created_at` |
| `playbook_items` | `id`, `version_id`, `item_key` (`REQ-1`, `F-1`, `UX-2`, `G-1`, `EC-1`, `RX-1`, or a `flow_key`), `category`, `title`, `body` (jsonb), `content_hash` |
| `item_links` | `version_id`, `from_key`, `to_key`, `relation` (`covers`, `verifies`, `checks`, `applies_to`) |

### Runs

| Table | Key fields |
|---|---|
| `runs` | `id`, `app_id`, `playbook_version_id`, `mode`, `trigger` (`manual`, `replay`), `replay_of_run_id`, `status`, `started_at`, `finished_at`, `environment` (jsonb: base_url, bug flags, browser version, Jev and Claude model versions), `totals` (jsonb) |
| `flow_runs` | `id`, `run_id`, `flow_key`, `variant_of` (for edge-case variants), `status`, `step_count`, `duration_ms`, `failure_reason` |
| `steps` | `id`, `flow_run_id`, `seq`, `intent`, `action_id`, `action_label`, `target_bbox` (jsonb), `page_tag`, `url`, `status`, `artifacts_complete` |
| `step_timings` | `step_id`, `observe_ms`, `extract_ms`, `decide_ms`, `gate_ms`, `act_ms`, `settle_ms`, `verify_ms` |
| `decisions` | `id`, `step_id`, `decider`, `model_version`, `question`, `choice`, `probabilities` (jsonb), `confidence`, `branch`, `latency_ms`, `input_tokens`, `output_tokens`, `input_hash`, `few_shot_ids[]`, `request` (jsonb), `response` (jsonb) |
| `check_results` | `id`, `flow_run_id`, `step_seq`, `check_key` (`F-1`, `UX-2`, `expect:2`, `EC-1`), `kind` (`formula`, `ux_rule`, `ux_judged`, `expectation`, `network`, `timing`), `pass`, `expected`, `actual`, `inputs` (jsonb: the bound values and where each came from), `judged_by` (`code`, `jev`, `claude`), `confidence` |
| `network_calls` | `id`, `flow_run_id`, `step_seq`, `method`, `url`, `status`, `duration_ms`, `req_size`, `resp_size`, `is_api`, `initiator` (jsonb), `traceparent`, `req_artifact_id`, `resp_artifact_id` |
| `artifacts` | `id`, `run_id`, `flow_run_id`, `step_seq`, `kind`, `object_key`, `content_type`, `size_bytes`, `sha256`, `uploaded_at` |
| `spans` | `trace_id`, `span_id`, `parent_span_id`, `run_id`, `name`, `kind`, `start_ns` (BIGINT), `end_ns` (BIGINT), `attributes` (jsonb), `status` |
| `log_entries` | `id`, `run_id`, `flow_run_id`, `step_seq`, `level`, `source` (`agent`, `console`, `pageerror`), `message`, `data` (jsonb), `ts` |
| `events` | `run_id`, `seq`, `type`, `payload` (jsonb), `ts`. Primary key `(run_id, seq)`. Append-only. |

### Findings, issues, and reports

| Table | Key fields |
|---|---|
| `findings` | `id`, `run_id`, `flow_run_id`, `step_seq`, `check_result_id`, `severity`, `kind`, `title`, `expected`, `actual`, `requirement_keys[]`, `fingerprint`, `issue_id` |
| `evidence_links` | `finding_id`, `kind` (`screenshot_before`, `screenshot_after`, `annotated`, `wait_frame`, `dom`, `network_call`, `console`, `span`, `decision`, `trace`), `ref_id`, `note` |
| `issues` | `id`, `app_id`, `fingerprint`, `title`, `severity`, `status` (`open`, `resolved`, `regressed`), `requirement_keys[]`, `first_seen_run_id`, `last_seen_run_id`, `occurrences`, `last_pass_run_id` |
| `reports` | `id`, `app_id`, `run_id`, `kind` (`run`, `bug`), `issue_id`, `status` (`generating`, `ready`, `failed`), `content` (jsonb), `markdown_artifact_id`, `html_artifact_id`, `pdf_artifact_id`, `model_version`, `generated_at` |
| `recommendations` | `id`, `report_id`, `category` (`functional`, `ux`, `performance`, `accessibility`, `test_coverage`), `text`, `rationale`, `evidence_finding_ids[]`, `requirement_keys[]`, `confidence` (`high`, `medium`, `low`), `effort` (`s`, `m`, `l`) |

### LangGraph checkpoint tables

Created by `AsyncPostgresSaver.setup()` in the `langgraph` schema (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`). One thread per flow run (`thread_id = flow_run_id`).

### Rules and indexes

- A run pins a `playbook_version_id`. Editing a playbook creates a new version and never changes past runs.
- `flow_key` and every item ID must stay stable across versions for history and issue tracking to work.
- Indexes:
  - `flow_runs (flow_key, run_id)` for per-flow history.
  - `runs (app_id, started_at desc)` for the run history table.
  - `events (run_id, seq)` for SSE resume.
  - `findings (fingerprint)` and `issues (app_id, fingerprint)` for deduplication.
  - `item_links (version_id, to_key)` for the traceability matrix.

---

## 7. Object storage

Bucket: `qagent-artifacts`, private. Preflight creates it with `CreateBucket` if `HeadBucket` says it doesn't exist.

Key layout:

```
apps/{app_id}/runs/{run_id}/
  manifest.json                                 every artifact in the run with its sha256
  flows/{flow_key}/
    trace.zip  har.json  console.jsonl
    steps/{seq}/before.jpg  after.jpg  annotated.jpg  dom.html  a11y.json  candidates.json
    steps/{seq}/wait/{n}.jpg
    network/{call_id}/request.json  response.json
  reports/run.md  run.html  run.pdf
  reports/issues/{issue_id}.md  {issue_id}.html
```

Upload pipeline:

1. The engine hands each file to `upload_queue` and keeps going, so uploads never slow a step.
2. A background worker uploads the file, computes its sha256, and inserts the `artifacts` row.
3. When a step's last upload finishes, the worker sets `steps.artifacts_complete` and emits an `artifact.uploaded` event.
4. Uploads retry with backoff. A failed upload is logged as a warning and never fails the run.
5. When a run finishes, `manifest.json` is written last, listing every artifact and its hash.

Serving files to the browser:

- **Images, trace.zip, and PDFs**: the API returns short-lived presigned GET URLs, which work directly in `<img src>` and download links.
- **JSON, HTML, and text** (network bodies, DOM, logs, report HTML): proxied through `GET /artifacts/{id}/content`. Browser `fetch()` of a presigned URL needs CORS rules on the bucket, and Neon's S3 compatibility may not support setting them, so proxying avoids the problem.
- With no storage credentials configured, the backend falls back to local disk (`LOCAL_ARTIFACT_DIR`, default `backend/.artifacts/`) and serves files itself.

Size controls: JPEG screenshots at quality 70, network bodies capped at 256 KB, and a P2 per-app retention setting.

---

## 8. Run engine

### LangGraph graph (one flow)

```
plan → begin_step → observe → decide → gate ─┬→ act → settle → verify ─┬→ begin_step (loop)
                                              ├→ escalate → gate        └→ finish
                                              └→ settle (step failed/blocked) → verify → finish
```

Each flow is one `StateGraph` execution with its own browser and checkpoint thread. State is a JSON-serializable `TypedDict` (`FlowState`); live objects (page, sandbox, recorder) travel in `config["configurable"]["rt"]` and are never checkpointed. Model calls are `RunnableLambda`s named `model:<Decider>`, and a `SpanCallbackHandler` turns node and model runs into spans.

| Node | Does |
|---|---|
| `plan` | Claude turns the flow into concrete step intents and fills in any test data the playbook leaves implicit. Its prompt includes the flow's requirements, the gotcha notes, and up to 3 reasoning examples with scope `planner`. Runs once per flow; its output is recorded. *(Today: validates the flow only.)* |
| `observe` | Captures the page state, the before screenshot, DOM, and accessibility snapshot. |
| `decide` | One Jev request per step with batched questions: `next_action` (choice over candidate IDs plus `STEP_DONE` and `STUCK`), `prev_step_ok` (noul), `risky` (noul), and any judged UX questions that apply to this page (noul). |
| `gate` | Confidence of at least `GATE_AUTO_MIN` proceeds. Between `GATE_ESCALATE_MIN` and that goes to `escalate`. Below it, or `STUCK`, fails the step. If `risky` is above 0.7, the action is blocked. |
| `escalate` | Claude chooses from the same option set, with reasoning examples of scope `escalation`. Its decision is logged with `branch=escalated`, and the result goes back through `gate`. When an escalator exists, low-confidence steps escalate too, rather than halting. |
| `act` | Resolves the chosen ID to its locator, records the target's bounding box, and runs the action. Typed values come only from test data. |
| `settle` | Waits for network idle (up to 5 s), or for the response named in a matching gotcha's `wait_for`. Captures wait frames every 500 ms while waiting longer than 1 s, then the after screenshot. |
| `verify` | Runs every check that applies at this step (see below) and writes one `check_results` row each. A failed check creates a finding. |
| `finish` | Writes the flow result and totals. Evaluates formulas against the final state. |
| *(after run)* `report` | The report engine runs once per run, outside the per-flow graph (section 10). |

Checks run in `verify`:

- The flow's **Expect** items: DOM checks, phrased as `noul` questions to Jev over the page text, with escalation to Claude in the middle band.
- The flow's `checks:` list: formulas (code), rule-based UX rules (code), judged UX rules (Jev, then Claude).
- Edge-case expectations, for variant flows.
- **Network checks**: any API call to an allowlisted host returning 5xx is a finding. 4xx is a finding unless the step expected an error.
- **Timing checks**: any API call slower than 2 s, and any `max_wait` rule violation.

Every check result records its inputs and where each came from. For F-1 that means the value of `subtotal` and the network call ID it was read from, the value of `total` and the screenshot and DOM it was read from. That is the basis of traceability.

**Confidence on noul answers**: Jev returns no confidence field for them, so gating uses `abs(p - 0.5) * 2`. For `choice` answers Jev returns `confidence` and per-choice `probabilities` directly.

### Extractor

- Collects buttons, links, inputs, selects, and elements with role attributes.
- Ranks them by visibility and closeness to the current intent, and keeps at most 40.
- Gives each a short ID (`a1…a40`) with a description like `button "Add to cart" in card "Blue Mug"`. Labels that repeat on a page are disambiguated with the surrounding row's text.
- Keeps the locator map on the server. Bounding boxes are stored for screenshots and the UI overlay but never sent to Jev.

### Budgets, cancel, checkpointer

- 25 steps and 90 seconds per flow. A cancel flag is checked at the start of every step.
- Checkpointer: `AsyncPostgresSaver` on the direct connection, in the `langgraph` schema (in-memory saver when no Postgres direct URL is set, as in tests). Checkpoints let you inspect a flow's state at every super-step; a browser cannot be resumed after a crash, so a flow restarts rather than resumes.

### Determinism

- Fixed viewport (1280×800), animations disabled, and the browser clock frozen with Playwright's clock API.
- Before every flow the engine calls the demo shop's `POST /__reset`, and the shop uses a seeded RNG.
- `RecordingDecider` stores every Jev and Claude call, including which reasoning examples were included. `ReplayDecider` serves them back by step and input hash, emitting a `divergence` event if the page's input hash differs from the recording.
- The Jev model version is pinned, and the version the API reports is stored with each decision.

---

## 9. Capture and traceability

### What is captured

| Captured | When | Stored in |
|---|---|---|
| Before and after screenshots | Every step | Object storage + `artifacts` |
| Annotated screenshot (target element boxed, step number in the corner) | Every step that has a finding; generated after the run | Object storage |
| Wait frames | Every 500 ms while settling more than 1 s | Object storage |
| DOM + accessibility snapshot + candidate list | Every step | Object storage |
| API calls (fetch/XHR to allowlisted hosts), with initiator and `traceparent` | Continuously, linked to the current step | `network_calls` + bodies in object storage |
| Playwright trace (`trace.zip`) | Per flow, with screenshots and snapshots enabled | Object storage |
| HAR | Per flow (`record_har_path`, bodies omitted) | Object storage |
| Console messages, page errors, failed requests | Continuously | `log_entries` + `console.jsonl` |
| Step timing breakdown | Every step | `step_timings` |
| Model calls (the tape) | Every decision | `decisions` |
| Check results with their bound inputs | Every check | `check_results` |
| Spans: run → flow → {observe, decide → model, gate, escalate, act, settle, verify}, plus one per check | Continuously | `spans` |
| Agent logs (structlog JSON, tagged with `run_id`, `flow_run_id`, `step_seq`) | Continuously | stdout + `log_entries` (info and above) |

**Redaction**: `authorization`, `cookie`, and `set-cookie` headers are always masked. Each app can add JSON keys to mask in bodies (for example `email`, `card`).

### How each piece of evidence is tied together

- **Step attribution.** A network call belongs to the step during whose `act` or `settle` phase it started. Calls outside any step (for example, background polling) are attached to the nearest previous step and marked `background`.
- **Correlation header (P1).** With `QAGENT_INJECT_TRACEPARENT=true`, the browser adds a W3C `traceparent` header to requests to allowlisted hosts, carrying QAgent's trace ID and the current step's span ID. If the target app uses OpenTelemetry, its server-side spans join the same trace. The demo shop logs the header so the link can be shown in the demo.
- **The evidence graph.** Every finding has `evidence_links` to its before, after, and annotated screenshots, the network calls that supplied its inputs, any console errors during that step, the decisions that led to that step, the step's span, and the flow's `trace.zip`. Every finding also carries the requirement IDs it violates, taken from the playbook links.
- **The traceability matrix.** Requirements → flows, formulas, UX rules, and edge cases (from `item_links`) → check results per run → findings → issues. One API call returns it for an app and playbook version, and the frontend renders it as a table.
- **Integrity.** Each artifact has a `sha256`, and the run's `manifest.json` lists them all. A report includes the run ID, the playbook version hash, and the manifest hash, so anyone can verify that the evidence wasn't changed.

---

## 10. Reports

There are three outputs: **bug reports** (one per issue), a **run report** (one per run, with recommendations), and the **live issues list** per app.

### From findings to issues (deduplication)

- A **finding** is one failed check in one run.
- An **issue** is the underlying bug, tracked across runs.
- Each finding gets a **fingerprint**: a hash of `check_key` + `flow_key` (without the variant suffix) + `kind` + a normalized locus (the endpoint path with IDs stripped, or the check's UI selector).
- When a run finishes, findings with a known fingerprint attach to the existing issue, and new fingerprints open a new issue.
- An open issue whose check passes in a later run is marked `resolved`. A resolved issue that fails again is marked `regressed`.
- This is what gives the demo its "the history turns from red to green" moment.

### Bug report contents (one per issue)

Everything except the narrative fields is assembled by code from stored facts.

| Section | Source |
|---|---|
| Title | Code template (for example `F-1 cart_total mismatch on /cart`), optionally polished by Claude |
| Severity and priority | The check's severity, raised to the requirement's priority if higher; judged findings capped at medium |
| Violated requirements | `REQ-` IDs with their PRD references and acceptance criteria |
| Environment | App URL, playbook version and hash, run ID, browser version, model versions, bug flags |
| Steps to reproduce | Generated by code from the recorded actions (`1. Open /products 2. Click "Add to cart" on "Blue Mug" …`). Never written by a model. |
| Expected vs actual | From the check result, including every bound input and where it came from (for example `subtotal = 40.00 from GET /api/cart`) |
| Evidence | Annotated screenshot, before and after screenshots, the API calls with status and a body excerpt, console errors, a link to `trace.zip`, a link to the step in the run viewer |
| Reproducibility | Seen in N of the last M runs; first seen and last seen |
| Impact (narrative) | Claude, 1–3 sentences |
| Suspected cause (narrative) | Claude, explicitly labeled a hypothesis, citing evidence IDs |
| Replay | A link that opens the run's replay at the failing step (P2) |

### Run report contents

- **Summary**: pass and fail counts per flow, new, recurring, resolved, and regressed issues, and total duration and cost.
- **Requirements coverage**: each `REQ-` with its status (covered and passing, covered and failing, or not covered).
- **Findings by category**: functional, formula, UX, performance, network, accessibility.
- **Performance**: the slowest API calls and longest waits, with links to the wait frames.
- **Recommendations**: see below.
- **Test-quality notes**: steps that needed escalation, low-confidence decisions, and divergences. These suggest where the playbook needs a gotcha or reasoning example.
- **Appendix**: links to every bug report and the run's manifest hash.

### How recommendations are generated, and kept honest

1. Code builds a **fact pack**: the run's findings with IDs, check results, timings, the requirement coverage table, and the playbook's gotchas and reasoning examples with scope `report`.
2. Claude receives only the fact pack and must answer with forced tool use in this shape: `{category, text, rationale, evidence_finding_ids[], requirement_keys[], confidence, effort}`.
3. A **grounding check** in code (`reports/grounding.py`) rejects any recommendation that cites no finding, cites an ID not in the fact pack, or references a requirement that doesn't exist. Rejected items are logged and dropped, never shown.
4. Recommendations are stored in `recommendations` with their links, so the UI can jump from a recommendation to its findings and from there to the evidence.
5. The Claude call is recorded on the tape like every other model call, so regenerating a report from a replayed run gives the same result.

Recommendation types:

- **Fixes** for the app, tied to findings ("Apply the discount before computing tax in the cart total").
- **UX improvements**, tied to UX findings and wait frames.
- **Test improvements** for the playbook ("REQ-4 has no flow covering it", "add a gotcha for the cart badge's async update to stop false positives").

### Generation and export

- Report generation starts automatically when a run finishes, as a background task. It emits `report.generating` and `report.ready` events.
- If Bedrock fails, the report is still produced with the code-built sections, and the narrative sections say "not generated".
- Formats:
  - **JSON** (the `content` field; the frontend renders from this).
  - **Markdown**, for pasting into an issue tracker.
  - **HTML** (Jinja template with embedded screenshots).
  - **PDF** (P1): the HTML printed with Playwright's `page.pdf()`.
- A **Copy as issue** button (P1) puts the bug report Markdown on the clipboard. Direct export to GitHub or Linear is P2.

---

## 11. API

Target API surface. Section 16 marks which routes exist today and where the current paths differ.

```
GET    /health                                    Jev, Bedrock, Postgres, object storage status

GET    /apps                                      with last-run summary, pass rate, open issue count
POST   /apps                                      {base_url, name?}  (name from hostname if missing)
GET    /apps/{app_id}
PATCH  /apps/{app_id}
DELETE /apps/{app_id}
POST   /apps/{app_id}/prd/extract                 (P1) Claude proposes REQ- items from the PRD

GET    /apps/{app_id}/playbooks
POST   /apps/{app_id}/playbooks                   upload .md -> {playbook, version, parsed, errors, warnings, coverage}
GET    /playbooks/{pb_id}                         with versions
GET    /playbook-versions/{version_id}/items?category=
POST   /playbooks/{pb_id}/versions                confirm edited Markdown -> new version
POST   /playbooks/{pb_id}/normalize               (P1) Claude rewrite -> proposed Markdown + diff

GET    /apps/{app_id}/flows                       current flows and variants + last 10 results each
GET    /apps/{app_id}/flows/{flow_key}/history

GET    /apps/{app_id}/runs                        paginated history
POST   /apps/{app_id}/runs                        {playbook_id, flow_keys?, include_edge_cases, mode} -> {run_id}
GET    /runs/{run_id}                             run + flow runs + totals + environment
GET    /runs/{run_id}/events                      SSE, supports Last-Event-ID
POST   /runs/{run_id}/stop
POST   /runs/{run_id}/replay                      re-run from the decision tape, with overrides
GET    /runs/{run_id}/steps?flow_key=             steps + timings + decisions
GET    /runs/{run_id}/checks?flow_key=&pass=      check results with inputs
GET    /runs/{run_id}/findings
GET    /findings/{finding_id}/evidence            the evidence graph for one finding
GET    /runs/{run_id}/network?flow_key=&is_api=&min_status=
GET    /network/{call_id}                         metadata + body artifact IDs
GET    /runs/{run_id}/spans
GET    /runs/{run_id}/logs?level=&source=&flow_key=

GET    /apps/{app_id}/issues?status=&severity=
GET    /issues/{issue_id}                         with occurrences across runs
GET    /apps/{app_id}/traceability?version_id=    requirements matrix

GET    /runs/{run_id}/report                      run report (JSON content + artifact IDs)
POST   /runs/{run_id}/report                      regenerate
GET    /issues/{issue_id}/report                  bug report
GET    /reports/{report_id}/export?format=md|html|pdf

GET    /artifacts/{artifact_id}/url               presigned GET (images, trace.zip, PDF)
GET    /artifacts/{artifact_id}/content           proxied (JSON, HTML, text)

GET    /dev/sse-replay?file=run_events.jsonl      dev only: replays a recorded event file as SSE
```

The OpenAPI schema is exported to `frontend/src/lib/api/openapi.json`, and the frontend generates its types from it with `openapi-typescript`.

---

## 12. Events (SSE)

Every event has the shape `{run_id, seq, ts, type, flow_run_id?, payload}`.

| Type | Payload |
|---|---|
| `run.started` / `run.finished` | status, totals |
| `flow.started` / `flow.finished` | flow_key, variant_of, status, duration_ms, step_count, failure_reason |
| `step.observed` | seq, url, page_tag, before_artifact_id |
| `decision.made` | decider, model_version, question, choice, probabilities, confidence, branch, latency_ms, tokens, few_shot_ids |
| `action.executed` | action_id, action_label, target_bbox, duration_ms |
| `network.call` | call_id, method, url, status, duration_ms |
| `check.result` | check_key, kind, pass, expected, actual, judged_by |
| `finding.created` | finding_id, severity, kind, title, requirement_keys |
| `artifact.uploaded` | artifact_id, kind, step_seq |
| `report.generating` / `report.ready` | report_id, kind |
| `log` | level, source, message (warnings and above only, to keep the stream light) |
| `divergence` | step_seq, expected_hash, actual_hash |
| `error` | message |

The persistence sink writes each event to `events` before it is broadcast, and emits are serialized so sequence numbers never arrive out of order under parallel flows. On reconnect with `Last-Event-ID`, the server replays from Postgres and then switches to live. A finished run loads the same way, so the live view and the history view are one component.

*Naming note*: the events emitted today use the Coder-2-frozen B0 names (`RUN_STARTED`, `STEP_OBSERVED`, `DECISION_MADE`, `GATE_TRIGGERED`, `ACTION_EXECUTED`, `NETWORK_CALL`, `VERIFICATION_STEP`, `FINDING_DISCOVERED`, `FLOW_FINISHED`, `RUN_FINISHED`, `LOG_EMITTED`, `SPAN_ENDED`, `RUN_ERROR`). Moving to the dotted names above is a coordinated rename with Coder 2 (task B12).

---

## 13. Frontend

### Pages

```
/                                     Minimal home: left-aligned URL field + a dense table of apps (not cards)
/apps/new                             Prefilled from the home input; name, allowed hosts, optional PRD
/apps/[appId]                         Overview
/apps/[appId]/playbooks               List + upload
/apps/[appId]/playbooks/[pbId]        Category editor (see below) + raw Markdown view + version history
/apps/[appId]/flows                   All flows and variants: last 10 results as dots, median duration, flakiness
/apps/[appId]/flows/[flowKey]         One flow's history and recurring issues
/apps/[appId]/runs                    Run history table
/apps/[appId]/runs/[runId]            Live tracking / permanent record
/apps/[appId]/runs/[runId]/report     Run report
/apps/[appId]/issues                  Issues list (open, regressed, resolved)
/apps/[appId]/issues/[issueId]        Bug report + occurrences across runs
/apps/[appId]/traceability            Requirements matrix
/apps/[appId]/runs/[runId]/replay     (P2) Tape editor + Fix & Replay
/apps/[appId]/compare                 (P1) Hybrid vs baseline
/apps/[appId]/settings                Base URL, allowed hosts, mode, thresholds, redaction keys
```

### App layout

- Header: app name, URL, open issue count, and a **Run** button (pick a playbook, mode, and whether to include edge cases).
- Tabs: Overview, Playbooks, Flows, Runs, Issues, Traceability, Compare, Settings.
- Live banner: shown on every tab while a run is active, linking to it.

### Overview

Latest run status, pass-rate strip for the last 20 runs, requirement coverage summary (covered and passing / failing / uncovered), and the top open issues by severity.

### Playbook editor (`/apps/[appId]/playbooks/[pbId]`)

- Category tabs: Requirements, Flows, Formulas, UX rules, Gotchas, Edge cases, Reasoning examples. Each tab shows the item count.
- Each tab has an "Add" form and an "Existing items" list below it, following the structure of the reasoning-example form but with sentence-case labels (see Design direction):
  - **Requirements**: ID, title, PRD reference, acceptance criteria, priority.
  - **Flows**: name, covers, checks, severity, steps (one per line), expectations, test data.
  - **Formulas**: name, rule (monospace, validated live), source, bindings (a small table), tolerance, verifies.
  - **UX rules**: title, check type (dropdown), fields for that type, severity.
  - **Gotchas**: title, note, optional machine hints (`wait_for`, `ignore_console`).
  - **Edge cases**: title, applies to (flow picker), expected behavior, test data, covers, checks.
  - **Reasoning examples**: scenario, context and challenge (optional), chain-of-thought and strategy (numbered steps), scope (checkboxes).
- Inline validation next to each item (errors in red, warnings in amber), plus a coverage panel listing requirements that nothing covers.
- Raw Markdown toggle showing the whole file; edits in either view stay in sync.
- Confirm creates a new version. Version history lists past versions with a diff view.
- Extract from PRD (P1) proposes requirements for one-by-one acceptance.

### Run page (`/apps/[appId]/runs/[runId]`)

- Header: status, timer, Stop, a metrics strip (Jev calls, median Jev latency, Claude calls, escalations, cost), and a **View report** button once `report.ready` arrives.
- Left pane: flows and their edge-case variants, each with status and a live timer.
- **The tape** (the signature element, see Design direction): for the selected flow, a horizontal filmstrip of step frames with a decision track and a checks track beneath it.
- Tabs:
  - **Graph**: React Flow, with decision nodes colored by branch (auto, escalated, failed) and check nodes colored pass or fail.
  - **Checks**: every check result with its inputs and their sources.
  - **Network**: API calls table; clicking one shows the request and response JSON side by side.
  - **Trace**: span waterfall + "Download trace.zip".
  - **Logs**: filterable by level, source, and flow.
  - **Findings**: sorted by severity, each linking to its issue and evidence.
- **Step drawer** (opened from a screenshot): Before / After / Annotated toggle with a scrubber over wait frames · Decision (probabilities, branch, latency, reasoning examples used) · Checks · Network (calls during that step) · DOM · Timing (one bar per phase).

### Evidence navigation (traceability in the UI)

Every ID is a link, and every link opens the exact place it refers to:

- A requirement in the matrix → the checks that cover it → their latest results.
- A finding → its step drawer at that step, with the relevant network call highlighted.
- A formula failure → each bound input → the API response or screenshot it was read from.
- A recommendation → the findings it cites → their evidence.

### Reports in the UI

- **Run report page**: renders the report JSON with the sections from section 10, plus export buttons (Markdown, HTML, PDF).
- **Issue page**: the bug report, an occurrence timeline across runs, and **Copy as issue**.

### Design direction

**Subject, audience, job.** QAgent is an inspection instrument. PMs, testers, and developers use it to watch runs and prove bugs with evidence, and judges see it for five minutes. Its primary job is to make evidence easy to follow. The look comes from that world (test benches, film tape, signal traces, lab records), not from SaaS dashboard templates.

**What changed from the earlier plan.** The earlier style (white rounded cards on `#F5F5F7`, black pill buttons, uppercase labels copied from the reasoning-example form, "Site · Route" meta strings) is the default generated look. It is replaced by what follows.

**Palette.** Color carries meaning. Signal blue appears only where Jev, live state, or selection is involved.

| Name | Hex | Use |
|---|---|---|
| Steel | `#E8EBEE` | Page ground |
| Sheet | `#FAFBFB` | Panels, tables, inputs |
| Rule | `#C7CED5` | Borders and dividers |
| Graphite | `#1C2733` | Text, primary buttons |
| Signal blue | `#2F4FD8` | Jev decisions, live state, selection, focus ring |
| Pass | `#1F7A55` | Passing checks, resolved issues |
| Fail | `#B3261E` | Failing checks, open issues, errors |
| Escalated | `#A86A0B` | Escalations to Claude, warnings |
| Muted | `#66717D` | Secondary text, skipped items |

These become OKLCH tokens in Tailwind v4's `@theme`, replacing shadcn's default theme entirely. Components use tokens only, never raw hex or Tailwind's stock color names. Dark mode is P2; tokens are named by role so it can be added later.

**Type.**

- **IBM Plex Sans** for all interface text (weights 400, 500, 600). Its engineering roots suit an instrument, and it isn't one of the default families (Inter, Geist) that mark generated apps.
- **IBM Plex Mono** only for machine values: URLs, IDs (`REQ-1`, `a7`), JSON, selectors, and durations in tables. Never for labels.
- Scale: 12, 14, 16, 20, 28 px. Base 14 px with 1.45 line height. Report prose at 16 px with lines under 75 characters.
- Sentence case everywhere. No all-caps labels and no tracked-out eyebrow text.

**Layout.**

- Left-aligned throughout. Dense and table-first: apps, runs, issues, network calls, and checks are tables, not grids of cards.
- Two radii only: 4 px for controls and screenshots, 8 px for panels and dialogs. Borders separate things; shadows appear only on floating layers (menus, dialogs, drawers).
- Home page:

```
QAgent
Test a web app
[ http://localhost:8001                                ]  [Add app]

Apps
Name        URL               Last run    Last 20 runs        Open issues
Demo shop   localhost:8001    2 min ago   ▮▮▮▮▯▮▮▮▮▮▮▮▮▮▮▮▮   3
```

- Run page, a three-pane workbench with resizable panes:

```
┌ Flows ─────────┬ Tape ───────────────────────────────────┬ Inspector ─────────┐
│ add-to-cart  ✓ │ [1][2][3][4][5]  ◀ live                  │ Step 4             │
│   EC-1       ✗ │ ┃ ┃ ┃ ┃ ┃   decision track               │ Before / After     │
│ checkout     ● │ ✓ ✓ ✗ ✓     checks track                 │ Decision           │
│                ├─────────────────────────────────────────┤ Checks             │
│                │ Graph  Checks  Network  Trace  Logs      │ Network            │
└────────────────┴─────────────────────────────────────────┴────────────────────┘
```

**The one bold element: the tape.** The run timeline is drawn as a strip of film: step frames in sequence, a decision track underneath (one tick per Jev or Claude decision, colored by branch, with height showing confidence), and a checks track (pass and fail notches). Scrubbing the tape moves the inspector to that step. In replay mode it becomes the editor. Everything around it stays quiet.

**Motion.** One orchestrated moment: during a live run, new frames slide into the tape and their decision ticks draw in. Otherwise motion only answers a person's action (a drawer opens, a row expands, a toast confirms). No entrance animations on sections and no hover lift on cards. Respect `prefers-reduced-motion`.

**Writing.**

- Name things by what users see: "Start run", "Confirm version", "Copy as issue".
- A button and its result use the same verb: "Confirm version" leads to "Version 3 confirmed".
- Metadata goes in labeled columns, not strings joined with middle dots.
- Empty states say what to do next: "No playbooks yet. Upload a Markdown file to start."
- Errors say what happened and how to fix it, without apologizing.

**Avoid list** (checked in every review): the stock shadcn theme, Lucide icons, Inter or Geist, gradient borders and glows, emoji as icons, purple gradients, rows of identical stat cards, all-caps labels, middle-dot meta strings, arrows appended to button text, monospace labels, and numbered markers on content that isn't a sequence.

### Frontend libraries

| Need | Library | Why |
|---|---|---|
| Components | shadcn/ui CLI on Base UI primitives, restyled with our tokens | Component code is copied into the repo and owned; Base UI is now shadcn's default primitive layer. The stock theme is replaced on day one. |
| Styling | Tailwind v4 (`@theme` tokens in OKLCH) | Matches shadcn's current setup |
| Icons | Phosphor (`@phosphor-icons/react`): regular weight for UI, fill weight for status | Multiple weights let status icons stand apart from UI icons; avoids the default Lucide look |
| Fonts | `next/font` with IBM Plex Sans and IBM Plex Mono | Self-hosted, no layout shift |
| Server state | TanStack Query | Polling and caching |
| URL state | `nuqs` | Filters and the selected step live in the URL, so every evidence view can be shared as a link |
| Tables | TanStack Table + TanStack Virtual | Runs, network calls, logs, and checks can be long |
| Panes | `react-resizable-panels` | The run workbench |
| Graph | `@xyflow/react` + `elkjs` for automatic layout | Decision graph |
| Small charts | Hand-written SVG for sparklines, pass-rate strips, and timing bars; visx for the Compare view | Custom drawings avoid the stock chart-library look and stay small |
| Markdown editor | CodeMirror 6 (`@uiw/react-codemirror`, markdown mode) with lint markers for validation errors and highlighting for IDs | Much lighter than Monaco |
| Version diff | `@codemirror/merge` | Same editor for playbook diffs |
| Code and JSON | Shiki for read-only highlighting + a collapsible JSON tree for request and response bodies | Network tab and evidence views |
| Before/after | `react-compare-slider` | Step screenshots |
| Command palette | `cmdk` | Jump to any run, issue, requirement, or ID |
| Toasts | Sonner | Action confirmations |
| Motion | Motion (`motion/react`) | The tape and drawers |
| Forms | `react-hook-form` + `zod` | Playbook item forms |
| Report text | `react-markdown` + `remark-gfm` | Narrative fields in reports |

Not used: effect libraries such as Aceternity and Magic UI (built for marketing pages), MUI and Ant Design (their strong built-in look would fight ours), and stock Recharts styling. Claude Code pins every package to a current stable version when installing.

### Keeping Claude Code on-style

- `frontend/DESIGN.md` holds this section. `frontend/CLAUDE.md` repeats the rules and the avoid list in short form and says that new components must use tokens, never raw hex or stock Tailwind colors.
- `/dev/kitchen-sink` renders every component, every status, and the tape with real QAgent content (run IDs, `REQ-` IDs, real flow names). It is built in F0 and reviewed before any real page is built.
- Each page gets a review pass: take a screenshot, check it against the avoid list, and remove one element that doesn't carry information.

### Data fetching

- TanStack Query for REST, polling the app list and Overview every 5 s.
- `EventSource` only on the run page.

---

## 14. Demo shop (`demo-shop/`, port 8001)

Pages: `/products`, `/cart`, `/checkout`, plus `/api/cart` and `/api/checkout`. Plain server-rendered HTML with `data-testid` attributes, and no iframes, shadow DOM, or canvas. Carts and coupons are per browser session (cookie), so parallel flows don't collide. It logs the incoming `traceparent` header for each API request (P1).

| # | Bug | Caught by |
|---|---|---|
| 1 | Cart badge count disagrees with the cart contents | UX-1 (`consistent_value`, UI vs API) |
| 2 | Missing postal-code validation | EC-3 + UX-3 (judged) |
| 3 | Every 3rd payment request returns 500 (a counter, cleared by `/__reset`, so it's deterministic) | Network check |
| 4 | Infinite spinner after applying a coupon | UX-2 (`max_wait`) + wait frames |
| 5 | Tax applied before the discount, so the total is wrong | F-1 (formula, UI and API) |

Bugs are toggled with `DEMO_BUGS=1,2,3,4,5` or at runtime with `POST /__bugs {"1": false}`. `POST /__reset` clears carts and counters. `playbooks/checkout.md` is written to catch all five.

---

## 15. Work plan

### Step 0: preflight (Coder 1, first; `make doctor`)

- **Postgres**: connect with `psycopg` using both the pooled and the direct URL, and run `select version()`.
- **Object storage**: `HeadBucket`, then `CreateBucket` if missing; put, get, and delete a test object; generate a presigned URL and fetch it with `curl`.
- **Jev**: `GET /v1/models` lists the aliases (`jev-latest`, `jev-preview`). Send one real `POST /v1/systemone` with a `choice` question with the pinned `JEV_MODEL` and confirm the response shape. Record the concrete model version the API reports (aliases resolve to it).
- **Bedrock**: send one Converse call with forced tool use against the configured model or inference profile, in the configured region. Confirm the tool input comes back as JSON.
- **Browser**: launch Chromium (or installed Chrome) headless, load the demo shop, take a screenshot.
- Write the results and the pinned model versions to `ASSUMPTIONS.md`.

> The source text of this section was cut off after the Jev preflight item. The rest of Step 0 and the task tables below are reconstructed from the earlier plan plus the new scope, and should be reviewed.

### Coder 1: backend (`be` branch)

| Code | Pri | Task | Status | Done when |
|---|---|---|---|---|
| **B0** | P0 | Domain schemas, event models, fixture routes, `/dev/sse-replay`, OpenAPI export | ✅ | Coder 2 can generate types and replay a recorded run |
| **B1** | P0 | Neon engines, Alembic migrations, `objects.py`, upload queue | ✅ | `make migrate` passes; upload tests pass |
| **B2** | P0 | Decision layer: `JevDecider` (retry 429/529, semaphore, model-version capture), `Stub`, `Recording`, `Replay` | ✅ (Jev rewritten against the real System One API) | Unit tests pass against a recorded tape |
| **B3** | P0 | Playbook parser (`markdown-it-py` tokens), formula validation (`simpleeval`), sample playbook | ✅ (superseded by B12) | Parser and formula tests pass |
| **B4** | P0 | Browser: sandbox (trace, HAR, console, host allow-list), extractor (≤40), executor, network recorder, wait frames | ✅ | Extractor and sandbox tests pass |
| **B5** | P0 | Engine as a real **LangGraph** `StateGraph` + langchain-core runnables + callback spans + Postgres checkpointer; gating, budgets, structlog, persistence sink | ✅ | `qagent.cli run` writes rows, spans, checkpoints and artifacts |
| **B6** | P0 | Verification: DOM, network 5xx, formula, timing and settle checks | ✅ | Bugs 1, 3, 4 and 5 produce findings |
| **B7** | P0 | Real API: `RunManager`, SSE with resume, flows/findings/network/spans/logs/artifact routes, playbook upload | ✅ | A run started from the API streams and resumes |
| **B8** | P0 | Demo shop with 5 bugs, `/__reset`, `/__bugs` | ✅ | Toggling bugs changes findings |
| **B9** | P1 | `ClaudeDecider` (forced tool use), escalation in the graph, baseline mode, `/playbooks/normalize` | ✅ | Baseline and hybrid runs complete |
| **B10** | P1 | `make bench`: p50/p95 latency, cost per step, candidate scaling (10, 20, 40) | ✅ | Figures recorded in `ASSUMPTIONS.md` |
| **B11** | P2 | Replay endpoint with overrides | ✅ (Neon "pin for demo" branch not done) | Replay reproduces findings from the tape |
| **B12** | P0 | **Seven-category playbook format** (section 5): `parser.py`, `schema.py`, `validate.py`, `coverage.py`, `versioning.py`, `playbook_items` and `item_links` tables, `/playbooks/validate`, errors block upload | ✅ | `playbooks/checkout.md` parses into all categories; validation errors return 422 |
| **B13** | P0 | **Checks package** (`checks/`): formulas with tolerance and `verifies`; UX rules `consistent_value`, `format`, `max_wait`, `no_console_errors`, `a11y`, `judged`; judged expectations (Jev then Claude); network and timing checks; a `check_results` row per check with bound inputs and sources | ✅ | Every check writes a row; API bindings cite the recorded call |
| **B14** | P0 | **Edge-case variants** (`add-to-cart#EC-1`) and gotcha machine hints (`wait_for`, `ignore_console`) | ✅ | Variants run with their own test data and history |
| **B15** | P0 | **Findings → issues** dedupe: fingerprints, `issues` table, open/resolved/regressed | ✅ | Second run recurs; fixing bugs resolves; reintroducing regresses |
| **B16** | P0 | **Evidence graph**: `evidence_links`, before/after/annotated screenshots (Pillow), step attribution of network calls, `manifest.json` with sha256 | ✅ | `GET /findings/{id}/evidence` returns every linked artifact |
| **B17** | P0 | **Report engine**: bug reports (code-built facts), run report, steps-to-reproduce, grounded recommendations (`grounding.py`), MD/HTML/PDF export, `report.*` events | ✅ | Report generates after a run; ungrounded recommendations are dropped |
| **B18** | P0 | **Traceability + routes**: `/traceability`, `/issues`, `/reports`, app-scoped runs and flows, checks, steps, evidence, artifact `/url` and `/content` | ✅ | Frontend can render matrix, issues and reports |
| **B19** | P1 | Jev batched questions (`next_action` with `STEP_DONE`/`STUCK`, `risky`, `prev_step_ok`), noul confidence for judging, reasoning-example selection and tape ids, gotcha hints | 🟡 all built except the Claude **planner** (the `plan` node only validates) | Hybrid run uses one Jev call per step with batched questions |
| **B20** | P1 | PDF export, `traceparent` injection, axe-core a11y, PRD extraction, `make doctor` preflight | ✅ | Preflight passes; PDF opens |
| **B21** | P1 | Event-name migration to the dotted names in section 12 (coordinate with Coder 2) | ✅ backend (`divergence` added; `artifact.uploaded` not emitted) | Frontend consumes new names |

### Coder 2: frontend (`fe` branch)

| Code | Pri | Task | Done when |
|---|---|---|---|
| **F0** | P0 | Next.js 16 setup, Tailwind v4 OKLCH tokens, replaced shadcn theme, IBM Plex fonts, `DESIGN.md`/`CLAUDE.md`, generated API client, app shell, `/dev/kitchen-sink` | Typed client builds; kitchen sink reviewed |
| **F1** | P0 | Home (URL field + apps table), `/apps/new`, app layout with tabs and live banner, Overview | App creation works against the API |
| **F2** | P0 | Playbooks list, upload, category editor with Add cards, raw Markdown view (CodeMirror), inline validation, coverage panel, version history and diff | Uploading the sample shows all seven categories |
| **F3** | P0 | Run page against `/dev/sse-replay`: flows pane, the tape, Graph tab, step drawer | A recorded run plays back smoothly |
| **F4** | P0 | Checks, Network, Trace, Logs and Findings tabs | Each tab renders fixture data |
| **F5** | P1 | Runs history, Flows tab and flow history, Issues list and issue page, Settings | Navigation and history views complete |
| **F6** | P0 | Switch to the real API; error and empty states; evidence navigation links | Real run visible end to end |
| **F7** | P0 | Run report page, traceability matrix, bug report with Copy as issue and exports | Report and matrix render from real data |
| **F8** | P1 | Compare view (hybrid vs baseline), command palette | Comparison metrics render |
| **F9** | P2 | Replay tape editor; normalize diff view | Tape viewer operational |

### Sync points and git workflow

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
    commit id: "B1-B11: Engine, API, Demo"
    checkout main
    merge be id: "Sync 1: Engine Proven"
    checkout fe
    merge main id: "Sync 2: Switch to Real API"
    checkout be
    commit id: "B12-B18: Playbooks, Checks, Reports"
    checkout main
    merge be id: "Sync 3: Evidence & Reports"
    checkout fe
    merge main id: "F6-F7: End-to-End Live"
    checkout main
    merge fe id: "Sync 4: Demo Ready"
```

1. **Contracts frozen (after B0 + F0)**: the frontend builds against generated types and fixture routes. Changes to `domain/` need agreement; additive DTOs are fine.
2. **Engine proven (after B1–B8)**: a CLI run passes against the demo shop, with rows in Neon and artifacts in object storage. ✅
3. **Evidence and reports (after B12–B18)**: playbook categories, check results, issues, evidence graph and reports are served by the API.
4. **Demo ready (after B19–B20 + F5–F8)**: hybrid and baseline runs complete with benchmark numbers, reports export, and the traceability view works.

---

## 16. Implementation status (as built on the `be` branch)

What exists today, and where it differs from the target in sections 5–12. **55 backend tests pass**; a live hybrid run
(real Jev, Claude, Neon Postgres and object storage) produced 8 findings, 8 issues, 8 bug reports and a run report.

**Built and tested**

- **Demo shop** with five bugs, per-session carts, `/__reset`, `/__bugs`, `/__traces` (logs `traceparent`).
- **Engine**: LangGraph `plan → begin_step → observe → decide → gate → (escalate → gate) → act → settle → verify → finish`,
  parallel flows, budgets, cancel, host allow-list, Postgres checkpointer (`langgraph` schema), node and model spans via a
  LangChain callback handler, edge-case variants, W3C `traceparent` injection, gotcha hints (`wait_for`, `ignore_console`).
- **Playbooks**: seven categories with stable IDs, links, validation (errors block, warnings don't), coverage,
  content-hash versioning, items and links persisted per version, `/playbooks/validate`, Claude normalize and PRD extraction
  (proposals are kept only if their quote appears in the PRD).
- **Checks**: formulas (with tolerance), `consistent_value`, `format`, `max_wait`, `no_console_errors`, `a11y` (bundled axe-core),
  judged rules and expectations (Jev `noul`, escalating to Claude with screenshots), network 5xx/4xx, slow calls, settle and step timing.
  Every check writes a `check_results` row whose inputs record each bound value, its source, and the network call it came from.
- **Findings and issues**: requirement keys, severity raised to the requirement's priority (judged findings capped at medium),
  fingerprints, issues with open / resolved / regressed.
- **Evidence**: before, after and annotated screenshots, wait frames, DOM, network call bodies, decisions, spans, trace.zip,
  `manifest.json` with sha256 per artifact; the manifest hash is cited in reports.
- **Reports**: bug report per issue (steps to reproduce built from recorded steps, expected vs actual with inputs, evidence,
  reproducibility, Claude impact and suspected cause that must cite real evidence IDs) and a run report (flows, requirement
  coverage, findings by category, performance, recommendations grounded by `grounding.py`, test-quality notes); Markdown, HTML
  (screenshots embedded) and PDF export; `report.generating` / `report.ready` events end the SSE stream.
- **API** (41 paths): apps (with summary, PATCH, DELETE, derived names), app-scoped runs and flows, playbooks, runs, SSE with
  `?after=` and `Last-Event-ID`, steps, checks, findings, evidence, network (filters and detail), spans, logs, issues, reports,
  traceability, artifacts (by path and by id: `/url` and proxied `/content`), replay. All routes also answer under `/api`.
- **Decision layer**: Jev (System One API, batched questions), Claude (Bedrock Converse, forced tool use, images), Stub,
  Recording and Replay (divergence reported when the page differs from the tape).
- **Tooling**: `make doctor` preflight (Postgres pooled and direct, object storage with presign, Jev, Bedrock, browser), `make bench`.

**Known gaps and differences from the target**

| Area | Today | Target |
|---|---|---|
| Planner | `plan` node only validates the flow; steps run as written | Claude planner with reasoning examples |
| Judged check replay | Jev/Claude judge and report calls are not written to the tape, so a replay re-asks them | Recorded on the tape |
| Determinism | Fixed viewport; target reset once per run (`reset_path`), not before every flow (flows share the demo shop's payment counter) | Frozen clock, animations disabled, reset per flow |
| Uploads | `artifacts_complete` is set when a step is verified, not when its uploads finish; no `artifact.uploaded` event | Set by the upload worker, with the event |
| Retention, upload retry | Not built (a failed upload is swallowed) | Backoff retries, per-app retention (P2) |
| Redaction | App `redact_keys` are masked in stored request and response bodies; headers are never stored | Same |
| API paths | Both flat (`/runs`, `/playbooks`) and app-scoped paths exist | App-scoped only |
| Neon branch pin | Not done | "Pin for demo" (P2) |
| Existing Neon data | Events written before the dotted-name migration keep the old uppercase names | n/a |

**Environment notes**

- Jev accepts the concrete version `jev-1.13.0` and the aliases `jev-latest` / `jev-preview`, which currently resolve to it. The earlier 400 errors came from a wrong request shape, not the model name.
- The dev project's object storage bucket is `captures`; `qagent-artifacts` does not exist there (preflight creates a missing bucket).
- The Playwright Chromium download can time out on restricted networks; the sandbox then falls back to installed Google Chrome.
- Tests and CLI runs write to the Neon database configured in `.env`; engine and API tests use a per-test SQLite file.
