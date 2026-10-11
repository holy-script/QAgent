import { describe, expect, it } from "vitest";
import { EventTranslator, toFlowHistory, toPlaybook, toRun, toTotals, toWarnings } from "@/lib/api/adapter";
import { makeRun } from "@/lib/api/fixtures";

describe("backend DTOs -> UI shapes", () => {
  it("maps run totals and statuses", () => {
    expect(toTotals({ total_steps: 25, findings_count: 4, jev_decisions: 15, claude_decisions: 2, total_cost_usd: 0.02, avg_decision_latency_ms: 920 }))
      .toMatchObject({ steps: 25, findings: 4, jev_decisions: 15, claude_decisions: 2, cost_usd: 0.02, p50_decide_ms: 920 });
    expect(toRun({ id: "r", app_id: "a", mode: "hybrid", trigger: "manual", status: "pending", totals: {} }, "Plan")).toMatchObject({ status: "queued", playbook_name: "Plan" });
    expect(toTotals(undefined).steps).toBe(0);
  });
  it("turns backend errors and warnings into editor messages", () => {
    expect(toWarnings(["bad"], ["meh"])).toEqual([{ line: 0, level: "error", message: "bad" }, { line: 0, level: "warning", message: "meh" }]);
  });
  it("builds a playbook with versions and parsed journeys", () => {
    const pb = toPlaybook({ id: "p", app_id: "a", name: "N", current_version_id: "v1", status: "confirmed" }, [{
      id: "v1", version_no: 1, raw_markdown: "# x", content_hash: "h", created_at: "t", errors: [], warnings: ["w"],
      parsed: { title: "T", base_url: "http://x", flows: [{ key: "j", severity: "high", steps: ["Open /a"], expect: [], test_data: { q: 2 }, checks: ["F-1"] }], formulas: [{ key: "F-1", title: "total", rule: "a == b", bindings: { a: "ui:x" } }], edge_cases: [{ key: "EC-1", title: "odd", applies_to: "j" }] },
    }]);
    expect(pb.versions[0].parsed.flows[0]).toMatchObject({ key: "j", test_data: { q: "2" }, edge_cases: ["EC-1: odd"] });
    expect(pb.versions[0].parsed.flows[0].formulas[0]).toMatchObject({ name: "F-1 total", expr: "a == b" });
    expect(pb.versions[0].warnings).toEqual([{ line: 0, level: "warning", message: "w" }]);
  });
  it("summarises flow history", () => {
    const h = toFlowHistory([{ flow_key: "j", severity: "high", last_results: [{ run_id: "r1", status: "passed_with_findings", duration_ms: 5, started_at: "t" }] }], new Map([["r1", "stub" as const]]));
    expect(h[0].runs[0]).toMatchObject({ run_id: "r1", mode: "stub", status: "failed", findings: 1 });
  });
});

describe("EventTranslator: one run, event by event", () => {
  const run = makeRun("run-x", "hybrid");
  const env = (seq: number, type: string, payload: Record<string, unknown>) => ({ seq, type, payload, ts: new Date(1_700_000_000_000 + seq * 100).toISOString() });
  const tr = () => new EventTranslator(run, "http://api");

  it("walks a step from observed to verified, attaching checks that arrive later", () => {
    const t = tr();
    expect(t.translate("run.started", env(1, "run.started", {}))[0]).toMatchObject({ type: "run.started" });
    expect(t.translate("flow.started", env(2, "flow.started", { flow_key: "j", severity: "high" }))[0]).toMatchObject({ type: "flow.started", payload: { flow_key: "j", severity: "high" } });
    const obs = t.translate("step.observed", env(3, "step.observed", { flow_key: "j", step_seq: 1, intent: "Open /a", url: "u", page_title: "Home", candidates_count: 0 }))[0];
    expect(obs).toMatchObject({ type: "step.observed", payload: { step: { seq: 1, status: "running", page_tag: "Home" } } });
    const dec = t.translate("decision.made", env(4, "decision.made", { flow_key: "j", step_seq: 1, decider: "jev", tier: "ESCALATE", branch: "escalated", selected_action_id: 2, action_label: "Add", confidence: 0.6, probabilities: { 2: 0.6 } }))[0];
    expect(dec).toMatchObject({ type: "step.decided", payload: { decision: { branch: "ESCALATE", choice: "Add" }, action_id: 2 } });
    const ver = t.translate("step.verified", env(5, "step.verified", { flow_key: "j", step_seq: 1, status: "passed", timings: { act_ms: 5 }, url: "u" }));
    expect(ver.map((e) => e.type)).toEqual(["step.acted", "step.verified"]);
    expect(ver[1]).toMatchObject({ payload: { status: "ok", verified: [] } });
    expect((ver[1] as { payload: { screenshot: string } }).payload.screenshot).toContain("http://api/api/artifacts/run-x/flows/j/steps/1/screenshot.jpg");
    const chk = t.translate("check.result", env(6, "check.result", { flow_key: "j", step_seq: 1, check_key: "F-1", pass: false, actual: "nope" }));
    expect(chk[0]).toMatchObject({ type: "step.verified", payload: { verified: [{ assertion: "F-1", passed: false, message: "nope" }] } });
  });
  it("holds back checks for a step that has not been verified yet", () => {
    expect(tr().translate("check.result", env(1, "check.result", { flow_key: "j", step_seq: 9, check_key: "X", pass: true }))).toEqual([]);
  });
  it("translates findings, network calls, logs, spans and the end of the run", () => {
    const t = tr();
    t.translate("run.started", env(1, "run.started", {}));
    expect(t.translate("finding.created", env(2, "finding.created", { id: "f", flow_key: "j", step_seq: 1, severity: "high", kind: "network", title: "T", expected: "e", actual: "a", check_key: "network:POST /x", requirement_keys: ["REQ-2"], judged_by: "code", evidence: {} }))[0])
      .toMatchObject({ type: "finding", payload: { id: "f", evidence: { check_key: "network:POST /x", requirement_keys: ["REQ-2"] } } });
    expect(t.translate("network.call", env(3, "network.call", { call_id: "c", flow_key: "j", step_seq: 1, method: "POST", url: "u", status: 500, duration_ms: 1, is_api: true }))[0]).toMatchObject({ payload: { id: "c", status: 500 } });
    expect(t.translate("log", env(4, "log", { level: "warning", message: "m", source: "gate" }))[0]).toMatchObject({ payload: { level: "warn", ts: 300 } });
    const span = t.translate("span.ended", env(5, "span.ended", { span_id: "s", parent_span_id: null, name: "decide", kind: "node", start_ns: 1_700_000_000_200e6, end_ns: 1_700_000_000_400e6, status: "ok", attributes: { a: null, b: 1 } }))[0];
    expect(span).toMatchObject({ payload: { kind: "decide", start_ms: 100, end_ms: 300, attributes: { b: 1 } } });
    expect(t.translate("flow.finished", env(6, "flow.finished", { flow_key: "j", status: "passed_with_findings", duration_ms: 9 }))[0]).toMatchObject({ payload: { status: "failed" } });
    expect(t.translate("run.finished", env(7, "run.finished", { status: "failed", totals: { findings_count: 1 } }))[0]).toMatchObject({ type: "run.finished", payload: { status: "failed", totals: { findings: 1 } } });
    expect(t.translate("error", env(8, "error", { message: "boom" }))[0]).toMatchObject({ payload: { status: "error" } });
    expect(t.translate("artifact.uploaded", env(9, "artifact.uploaded", {}))).toEqual([]); // unknown events are ignored
  });
});

import { toTotals as totalsOf } from "../api/adapter";
describe("cost breakdown", () => {
  it("carries where the money went, defaulting to zero", () => {
    expect(totalsOf({ total_cost_usd: 0.05, judge_cost_usd: 0.01, report_cost_usd: 0.02 })).toMatchObject({ cost_usd: 0.05, judge_cost_usd: 0.01, planner_cost_usd: 0, report_cost_usd: 0.02 });
  });
});
