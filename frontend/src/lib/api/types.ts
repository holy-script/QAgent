// Hand-written stand-in for the generated OpenAPI types (`npm run gen:api` once B0 exports the schema).
// Field names follow the data model in DUAL_CODER_PLAN.md §5.

export type Mode = "hybrid" | "baseline" | "stub";
export type Severity = "low" | "medium" | "high" | "critical";
export type RunStatus = "queued" | "running" | "passed" | "failed" | "stopped" | "error";
export type Tier = "AUTO" | "ESCALATE" | "STOP";

export interface App {
  id: string;
  slug: string;
  name: string;
  base_url: string;
  allowed_hosts: string[];
  description: string;
  prd_markdown: string;
  default_mode: Mode;
  gate_overrides: { auto_min?: number; escalate_min?: number };
  redact_keys: string[];
  /** Finished runs older than this many days are cleaned up; null keeps them for ever. */
  retention_days: number | null;
  /** The newest runs that are always kept, whatever their age. */
  retention_keep_last: number;
  created_at: string;
}
export type AppInput = Pick<App, "name" | "base_url" | "description"> & Partial<App>;

export interface ParsedFormula {
  name: string;
  expr: string;
  source: "ui" | "api" | "both";
  bindings: Record<string, string>;
}
export interface ParsedFlow {
  key: string;
  severity: Severity;
  /** A high-level journey: the AI works out the steps itself. */
  goal?: string;
  /** "setup": the sign-in journey; it runs first and the others reuse its session. */
  role?: string;
  steps: string[];
  expect: string[];
  test_data: Record<string, string>;
  formulas: ParsedFormula[];
  edge_cases: string[];
}
export interface PlaybookWarning {
  line: number;
  level: "error" | "warning";
  message: string;
}
export interface PlaybookVersion {
  id: string;
  playbook_id: string;
  version_no: number;
  raw_markdown: string;
  parsed: { title: string; base_url: string | null; flows: ParsedFlow[] };
  warnings: PlaybookWarning[];
  content_hash: string;
  created_at: string;
}
export interface Playbook {
  id: string;
  app_id: string;
  name: string;
  current_version_id: string;
  status: "draft" | "confirmed";
  versions: PlaybookVersion[];
}

export interface RunTotals {
  steps: number;
  flows: number;
  findings: number;
  jev_decisions: number;
  claude_decisions: number;
  escalations: number;
  cost_usd: number;
  p50_decide_ms: number;
  p95_decide_ms: number;
  /** Where the cost went (real backend only): step decisions are cost_usd minus the rest. */
  judge_cost_usd?: number;
  planner_cost_usd?: number;
  report_cost_usd?: number;
}
export interface Run {
  id: string;
  app_id: string;
  playbook_version_id: string;
  playbook_name: string;
  mode: Mode;
  trigger: "manual" | "replay";
  replay_of_run_id: string | null;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  totals: RunTotals;
}

export interface Candidate {
  id: number;
  role: string;
  label: string;
  rect: [number, number, number, number]; // x, y, w, h in the 1280x800 viewport
}
export interface Decision {
  decider: "jev" | "claude" | "stub";
  model_version: string;
  question: string;
  choice: string;
  probabilities: Record<string, number>;
  confidence: number;
  branch: Tier;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
}
export interface StepTimings {
  observe_ms: number;
  extract_ms: number;
  decide_ms: number;
  gate_ms: number;
  act_ms: number;
  settle_ms: number;
  verify_ms: number;
}
export interface Step {
  flow_key: string;
  seq: number;
  intent: string;
  action_id: number | null;
  action_label: string;
  page_tag: string;
  url: string;
  status: "running" | "ok" | "failed";
  screenshot: string | null; // URL (presigned in prod, data URI in fixtures)
  wait_frames: string[];
  candidates: Candidate[];
  decisions: Decision[];
  timings: StepTimings | null;
  verified: { assertion: string; passed: boolean; message: string }[];
}
export interface FlowRun {
  flow_key: string;
  status: "pending" | "running" | "passed" | "failed";
  severity: Severity;
  duration_ms: number;
  failure_reason: string | null;
  steps: Step[];
}
export interface FlowHistory {
  flow_key: string;
  severity: Severity;
  runs: { run_id: string; mode: Mode; status: "passed" | "failed"; duration_ms: number; findings: number; started_at: string }[];
}
export interface Finding {
  id: string;
  flow_key: string;
  step_seq: number;
  severity: Severity;
  kind: "formula" | "dom" | "network" | "timing";
  title: string;
  expected: string;
  actual: string;
  evidence: Record<string, unknown>;
}
export interface NetworkCall {
  id: string;
  flow_key: string;
  step_seq: number;
  method: string;
  url: string;
  status: number;
  duration_ms: number;
  req_size: number;
  resp_size: number;
  is_api: boolean;
  request_body?: unknown;
  response_body?: unknown;
}
export interface Span {
  span_id: string;
  parent_span_id: string | null;
  name: string;
  kind: "run" | "flow" | "step" | "decide" | "act" | "verify";
  start_ms: number; // offset from run start
  end_ms: number;
  status: "ok" | "error";
  attributes: Record<string, string | number | boolean>;
}
export interface LogEntry {
  id: string;
  flow_key: string | null;
  step_seq: number | null;
  level: "debug" | "info" | "warn" | "error";
  source: string;
  message: string;
  ts: number; // offset ms
}

export type RunEvent =
  | { type: "run.started"; payload: { run: Run; flows: { key: string; severity: Severity }[] } }
  | { type: "flow.started"; payload: { flow_key: string; severity?: Severity } }
  | { type: "step.observed"; payload: { step: Step } }
  | { type: "step.decided"; payload: { flow_key: string; seq: number; decision: Decision; action_id: number; action_label: string } }
  | { type: "step.acted"; payload: { flow_key: string; seq: number; timings: StepTimings; wait_frames: string[] } }
  | { type: "step.verified"; payload: { flow_key: string; seq: number; status: "ok" | "failed"; verified: Step["verified"]; screenshot?: string } }
  | { type: "network.call"; payload: NetworkCall }
  | { type: "span"; payload: Span }
  | { type: "log"; payload: LogEntry }
  | { type: "finding"; payload: Finding }
  | { type: "flow.finished"; payload: { flow_key: string; status: "passed" | "failed"; duration_ms: number; failure_reason: string | null } }
  | { type: "run.finished"; payload: { status: RunStatus; totals: RunTotals; finished_at: string } };

export interface SseEnvelope {
  seq: number;
  ts: number; // ms offset from run start (fixtures) — used to pace replay
  event: RunEvent;
}

export interface RetentionStatus { retention_days: number | null; retention_keep_last: number; total_runs: number; would_delete: number; oldest_started_at: string | null }

/** A saved sign-in detail. Secret values are never sent back; only the name and that it is set. */
export interface Credential { name: string; secret: boolean; value: string | null; updated_at: string }

/** A file a test can upload through a page's file field. Built-in samples exist for every app. */
export interface TestFile { id: string; name: string; content_type: string; size_bytes: number; created_at: string; builtin: boolean }
