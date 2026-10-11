// Translates the backend's DTOs and SSE events (backend/openapi.json, DUAL_CODER_PLAN §11-12) into the
// shapes the UI was built against (./types). Used only when NEXT_PUBLIC_API_URL is set.
import type {
  App, Decision, Finding, FlowHistory, LogEntry, NetworkCall, ParsedFlow, Playbook, PlaybookVersion, PlaybookWarning,
  Run, RunEvent, RunStatus, RunTotals, Severity, Span, Step, StepTimings, Tier,
} from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type B = any;

export const toApp = (a: B): App => ({ ...a, description: a.description ?? "", prd_markdown: a.prd_markdown ?? "", retention_days: a.retention_days ?? null, retention_keep_last: a.retention_keep_last ?? 10 });

export const toTotals = (t: B = {}): RunTotals => ({
  steps: t.total_steps ?? 0, flows: t.flows ?? 0, findings: t.findings_count ?? 0, jev_decisions: t.jev_decisions ?? 0,
  claude_decisions: t.claude_decisions ?? 0, escalations: t.escalations ?? 0, cost_usd: t.total_cost_usd ?? 0,
  p50_decide_ms: t.avg_decision_latency_ms ?? 0, p95_decide_ms: t.avg_decision_latency_ms ?? 0,
  judge_cost_usd: t.judge_cost_usd ?? 0, planner_cost_usd: t.planner_cost_usd ?? 0, report_cost_usd: t.report_cost_usd ?? 0,
});

const runStatus = (s: string): RunStatus => (s === "pending" ? "queued" : (s as RunStatus));

export const toRun = (r: B, playbookName = "Playbook"): Run => ({
  id: r.id, app_id: r.app_id, playbook_version_id: r.playbook_version_id ?? "", playbook_name: playbookName, mode: r.mode,
  trigger: r.trigger, replay_of_run_id: r.replay_of_run_id ?? null, status: runStatus(r.status),
  started_at: r.started_at ?? new Date().toISOString(), finished_at: r.finished_at ?? null, totals: toTotals(r.totals),
});

const sev = (s: string): Severity => (["low", "medium", "high", "critical"].includes(s) ? (s as Severity) : "medium");

/** Backend parsed playbook (seven categories) -> the flow cards the review page renders. */
export function toParsedFlows(parsed: B): ParsedFlow[] {
  const formulas: B[] = parsed.formulas ?? [];
  const ecs: B[] = parsed.edge_cases ?? [];
  return (parsed.flows ?? []).map((f: B): ParsedFlow => ({
    key: f.key, severity: sev(f.severity), steps: f.steps ?? [], expect: f.expect ?? [],
    test_data: Object.fromEntries(Object.entries(f.test_data ?? {}).map(([k, v]) => [k, String(v)])),
    formulas: (f.checks ?? []).flatMap((k: string) => formulas.filter((x) => x.key === k)).map((x: B) => ({
      name: `${x.key} ${x.title ?? ""}`.trim(), expr: x.rule, source: x.source ?? "both", bindings: x.bindings ?? {},
    })),
    edge_cases: ecs.filter((e) => e.applies_to === f.key).map((e) => `${e.key}: ${e.title}`),
  }));
}

export const toWarnings = (errors: string[] = [], warnings: string[] = []): PlaybookWarning[] => [
  ...errors.map((message) => ({ line: 0, level: "error" as const, message })),
  ...warnings.map((message) => ({ line: 0, level: "warning" as const, message })),
];

export function toPlaybook(pb: B, versions: B[]): Playbook {
  const vs: PlaybookVersion[] = versions.map((v) => ({
    id: v.id, playbook_id: pb.id, version_no: v.version_no, raw_markdown: v.raw_markdown ?? "",
    parsed: { title: v.parsed?.title ?? pb.name, base_url: v.parsed?.base_url ?? null, flows: toParsedFlows(v.parsed ?? {}) },
    warnings: toWarnings(v.errors, v.warnings), content_hash: v.content_hash, created_at: v.created_at,
  }));
  return { id: pb.id, app_id: pb.app_id, name: pb.name, current_version_id: pb.current_version_id ?? "", status: pb.status, versions: vs };
}

export function toFlowHistory(flows: B[], runModes: Map<string, Run["mode"]>): FlowHistory[] {
  return flows.map((f) => ({
    flow_key: f.flow_key, severity: sev(f.severity),
    runs: (f.last_results ?? []).map((r: B) => ({
      run_id: r.run_id, mode: runModes.get(r.run_id) ?? "hybrid", status: r.status === "passed" ? "passed" : "failed",
      duration_ms: r.duration_ms, findings: r.status === "passed_with_findings" ? 1 : 0, started_at: r.started_at ?? "",
    })),
  }));
}

/** Backend event names that carry data the run view uses. */
export const EVENT_TYPES = [
  "run.started", "flow.started", "step.observed", "decision.made", "action.executed", "network.call", "step.verified",
  "finding.created", "flow.finished", "run.finished", "error", "log", "span.ended", "check.result",
  "report.ready", "report.failed", "divergence",
];

const noTimings: StepTimings = { observe_ms: 0, extract_ms: 0, decide_ms: 0, gate_ms: 0, act_ms: 0, settle_ms: 0, verify_ms: 0 };
const SPAN_KIND: Record<string, Span["kind"]> = { decide: "decide", act: "act", verify: "verify", flow: "flow" };

/**
 * Stateful per-stream translator: one backend envelope in, zero or more UI events out.
 * It remembers severities, step status and check results so a step's "verified" list can grow as
 * flow-level checks arrive after the last step.
 */
export class EventTranslator {
  private t0: number | null = null;
  private severity = new Map<string, Severity>();
  private steps = new Map<string, { status: "ok" | "failed"; verified: Step["verified"]; sent: boolean }>();
  constructor(private run: Run, private apiUrl: string) {}

  private offset(ts: string) { return this.t0 === null ? 0 : Date.parse(ts) - this.t0; }

  translate(type: string, env: B): RunEvent[] {
    const p = env.payload ?? {};
    if (this.t0 === null) this.t0 = Date.parse(env.ts);
    switch (type) {
      case "run.started":
        return [{ type: "run.started", payload: { run: { ...this.run, status: "running" }, flows: [] } }];
      case "flow.started":
        this.severity.set(p.flow_key, sev(p.severity));
        return [{ type: "flow.started", payload: { flow_key: p.flow_key, severity: sev(p.severity) } }];
      case "step.observed": {
        const step: Step = {
          flow_key: p.flow_key, seq: p.step_seq, intent: p.intent, action_id: null, action_label: "", page_tag: p.page_title || p.url,
          url: p.url, status: "running", screenshot: null, wait_frames: [], candidates: [], decisions: [], timings: null, verified: [],
        };
        return [{ type: "step.observed", payload: { step } }];
      }
      case "decision.made": {
        const tier: Tier = p.branch === "escalated" ? "ESCALATE" : (p.tier as Tier);
        const decision: Decision = {
          decider: p.decider, model_version: p.model_version ?? "", question: p.question ?? "", choice: p.action_label || String(p.selected_action_id),
          probabilities: Object.fromEntries(Object.entries(p.probabilities ?? {}).map(([k, v]) => [k, Number(v)])),
          confidence: p.confidence, branch: tier, latency_ms: p.latency_ms ?? 0, input_tokens: p.input_tokens ?? 0, output_tokens: p.output_tokens ?? 0,
        };
        return [{ type: "step.decided", payload: { flow_key: p.flow_key, seq: p.step_seq, decision, action_id: p.selected_action_id, action_label: p.action_label ?? "" } }];
      }
      case "network.call": {
        const call: NetworkCall = {
          id: p.call_id, flow_key: p.flow_key, step_seq: p.step_seq, method: p.method, url: p.url, status: p.status,
          duration_ms: p.duration_ms, req_size: p.req_size ?? 0, resp_size: p.resp_size ?? 0, is_api: !!p.is_api,
        };
        return [{ type: "network.call", payload: call }];
      }
      case "step.verified": {
        const key = `${p.flow_key}:${p.step_seq}`;
        const status = p.status === "passed" ? "ok" : "failed";
        const prev = this.steps.get(key);
        this.steps.set(key, { status, verified: prev?.verified ?? [], sent: true });
        const t = p.timings ?? {};
        const timings: StepTimings = { ...noTimings, ...t };
        return [
          { type: "step.acted", payload: { flow_key: p.flow_key, seq: p.step_seq, timings, wait_frames: [] } },
          { type: "step.verified", payload: { flow_key: p.flow_key, seq: p.step_seq, status, verified: this.steps.get(key)!.verified,
            screenshot: `${this.apiUrl}/api/artifacts/${this.run.id}/flows/${encodeURIComponent(p.flow_key)}/steps/${p.step_seq}/screenshot.jpg?v=${Date.now()}` } },
        ];
      }
      case "check.result": {
        const key = `${p.flow_key}:${p.step_seq}`;
        const cur = this.steps.get(key) ?? { status: "ok" as const, verified: [], sent: false };
        cur.verified = [...cur.verified, { assertion: p.check_key, passed: !!p.pass, message: p.pass ? (p.expected ?? "") : String(p.actual ?? "") }];
        this.steps.set(key, cur);
        if (!cur.sent) return [];
        return [{ type: "step.verified", payload: { flow_key: p.flow_key, seq: p.step_seq, status: cur.status, verified: cur.verified } }];
      }
      case "finding.created": {
        const f: Finding = { id: p.id, flow_key: p.flow_key, step_seq: p.step_seq, severity: sev(p.severity), kind: p.kind, title: p.title,
          expected: p.expected, actual: p.actual, evidence: { ...p.evidence, check_key: p.check_key, requirement_keys: p.requirement_keys, judged_by: p.judged_by } };
        return [{ type: "finding", payload: f }];
      }
      case "span.ended": {
        const t0 = (this.t0 ?? 0) * 1e6;
        const name = String(p.name);
        const kind: Span["kind"] = p.kind === "model" ? "decide" : p.kind === "flow" ? "flow" : SPAN_KIND[name] ?? "step";
        const span: Span = { span_id: p.span_id, parent_span_id: p.parent_span_id ?? null, name, kind,
          start_ms: (p.start_ns - t0) / 1e6, end_ms: (p.end_ns - t0) / 1e6, status: p.status === "error" ? "error" : "ok",
          attributes: Object.fromEntries(Object.entries(p.attributes ?? {}).filter(([, v]) => v !== null).map(([k, v]) => [k, v as string | number | boolean])) };
        return [{ type: "span", payload: span }];
      }
      case "log": {
        const level = p.level === "warning" ? "warn" : p.level;
        const l: LogEntry = { id: `${env.seq}`, flow_key: p.flow_key ?? null, step_seq: p.step_seq ?? null, level, source: p.source ?? "engine",
          message: p.message, ts: this.offset(env.ts) };
        return [{ type: "log", payload: l }];
      }
      case "flow.finished":
        return [{ type: "flow.finished", payload: { flow_key: p.flow_key, status: p.status === "passed" ? "passed" : "failed",
          duration_ms: p.duration_ms ?? 0, failure_reason: p.failure_reason ?? null } }];
      case "run.finished":
        return [{ type: "run.finished", payload: { status: p.status as RunStatus, totals: toTotals(p.totals), finished_at: env.ts } }];
      case "error":
        return [{ type: "run.finished", payload: { status: "error", totals: toTotals({}), finished_at: env.ts } }];
      default:
        return [];
    }
  }
}
