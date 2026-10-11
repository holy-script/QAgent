// Demo-mode data for the screens that need backend features (bugs, reports, requirements, proof, validation,
// suggestions, rewrite, repeat run). Everything is derived from the same scripted runs the run viewer replays, so the
// numbers on every page agree with each other.
import { api } from "./client";
import { shot } from "./fixtures";
import type { Evidence, Issue, IssueDetail, Proposal, Report, Traceability, Validation } from "./live";
import type { Run, SseEnvelope } from "./types";
import { validateMarkdown } from "../playbook-validate";

/* eslint-disable @typescript-eslint/no-explicit-any */
const APP = "app-demo-shop";
const RUNS = ["run-h1", "run-b2", "run-h3"]; // oldest first, as seeded in fixtures

interface Spec { id: string; title: string; status: "open" | "regressed" | "resolved"; severity: "medium" | "high" | "critical"; kind: string; check: string; flow: string; step: number; finding: string; runs: string[]; reqs: string[]; judged?: string }
const SPECS: Spec[] = [
  { id: "iss-badge", title: "UX-1 Cart count is consistent across the app violated", status: "open", severity: "medium", kind: "dom", check: "UX-1", flow: "add-to-cart", step: 2, finding: "f-add-to-cart-2", runs: RUNS, reqs: [] },
  { id: "iss-total", title: "F-1 cart_total failed", status: "regressed", severity: "high", kind: "formula", check: "F-1", flow: "add-to-cart", step: 3, finding: "f-add-to-cart-3", runs: ["run-h1", "run-h3"], reqs: ["REQ-1"] },
  { id: "iss-postal", title: "Expectation not met: An inline error appears and the address is not saved.", status: "open", severity: "medium", kind: "dom", check: "expect:checkout#EC-3:1", flow: "checkout", step: 2, finding: "f-checkout-2", runs: ["run-b2", "run-h3"], reqs: ["REQ-3"], judged: "jev" },
  { id: "iss-pay", title: "Server error on POST /api/pay", status: "open", severity: "critical", kind: "network", check: "network:POST /api/pay", flow: "checkout", step: 3, finding: "f-checkout-3", runs: RUNS, reqs: ["REQ-2"] },
  { id: "iss-spinner", title: "UX-2 No loading state lasts longer than 2.5 seconds violated", status: "resolved", severity: "high", kind: "timing", check: "UX-2", flow: "checkout", step: 3, finding: "f-checkout-3", runs: ["run-h1"], reqs: [] },
];

const runsById = async (): Promise<Map<string, Run>> => new Map((await api.listRuns("demo-shop")).map((r) => [r.id, r]));
const toIssue = (s: Spec, runs: Map<string, Run>): IssueDetail => {
  const last = runs.get(s.runs[s.runs.length - 1]);
  return {
    id: s.id, app_id: APP, fingerprint: `fp-${s.id}`, title: s.title, severity: s.severity, status: s.status, kind: s.kind, check_key: s.check,
    flow_key: s.flow, requirement_keys: s.reqs, first_seen_run_id: s.runs[0], last_seen_run_id: s.runs[s.runs.length - 1],
    last_pass_run_id: s.status === "resolved" ? "run-h3" : null, occurrences: s.runs.length, updated_at: last?.started_at,
    occurrence_list: s.runs.map((r) => ({ run_id: r, finding_id: s.finding, step_seq: s.step, severity: s.severity, started_at: runs.get(r)?.started_at })),
  };
};

async function eventsFor(runId: string): Promise<SseEnvelope[]> {
  const run = (await api.listRuns("demo-shop")).find((r) => r.id === runId) ?? (await api.getRun(runId));
  return api.mockEvents(run);
}
async function findingContext(findingId: string) {
  for (const id of RUNS) {
    const ev = await eventsFor(id);
    const f = ev.map((e) => e.event).find((e) => e.type === "finding" && e.payload.id === findingId);
    if (f && f.type === "finding") {
      const steps = ev.map((e) => e.event).filter((e) => e.type === "step.observed");
      const step = steps.map((e) => (e.type === "step.observed" ? e.payload.step : null)).find((s) => s && s.flow_key === f.payload.flow_key && s.seq === f.payload.step_seq);
      const calls = ev.map((e) => e.event).filter((e) => e.type === "network.call" && e.payload.flow_key === f.payload.flow_key && e.payload.step_seq === f.payload.step_seq);
      return { run: id, finding: f.payload, step, calls: calls.map((c) => (c.type === "network.call" ? c.payload : null)).filter(Boolean) as any[] };
    }
  }
  return null;
}

const STEPS: Record<string, string[]> = {
  "add-to-cart": ["Open /products", "Add 2 items to cart", "Go to /cart"],
  checkout: ["Open /checkout", "Fill shipping address", "Pay with test card"],
};
const REQS = [
  { key: "REQ-1", title: "Cart total applies the discount before tax", priority: "high", prd_ref: "§3.2 Pricing", acceptance: "total = (subtotal − discount) × (1 + tax_rate), rounded to 2 decimals", status: "covered_failing", items: ["F-1", "add-to-cart", "apply-coupon", "EC-2"], failing: ["iss-total"] },
  { key: "REQ-2", title: "Payments succeed reliably", priority: "critical", prd_ref: "§5.1 Payment", acceptance: "Every payment attempt with a valid cart returns success. No server errors.", status: "covered_failing", items: ["payment"], failing: ["iss-pay"] },
  { key: "REQ-3", title: "Checkout requires a valid postal code", priority: "high", prd_ref: "§4.1 Address form", acceptance: "Submitting without a postal code shows an inline error and blocks submission.", status: "covered_failing", items: ["checkout", "EC-3", "UX-3"], failing: ["iss-postal"] },
  { key: "REQ-4", title: "Orders can be cancelled before they ship", priority: "medium", prd_ref: "§6.2 Orders", acceptance: "A placed order can be cancelled until it ships.", status: "uncovered", items: [], failing: [] },
];

const issueContent = async (s: Spec) => {
  const ctx = await findingContext(s.finding);
  const f = ctx?.finding;
  const img = (kind: string, title: string) => ({ id: `${s.id}-${kind}`, kind, ref_id: `mock/${kind}`, note: "", available: true, artifact_id: null, src: shot(title, 1, [], null) });
  return {
    kind: "bug", issue_id: s.id, title: s.title, status: s.status, severity: s.severity, priority: s.reqs.length ? "high" : s.severity, judged_by: s.judged ?? "code",
    violated_requirements: REQS.filter((r) => s.reqs.includes(r.key)).map(({ key, title, prd_ref, acceptance, priority }) => ({ key, title, prd_ref, acceptance, priority })),
    environment: { app_url: "http://localhost:8001", run_id: s.runs[s.runs.length - 1], playbook_version_id: "pbv-2", browser: "chromium 153", models: { jev: "jev-1.13.0", claude: "claude-sonnet-4.6" }, bug_flags: { 1: true, 3: true, 5: true } },
    steps_to_reproduce: [...(STEPS[s.flow] ?? []).slice(0, s.step).map((t, i) => `${i + 1}. ${t}`)],
    expected_actual: {
      check_key: s.check, expected: f?.expected ?? "", actual: f?.actual ?? "",
      inputs: s.check === "UX-1" ? [{ name: "target_1", value: 1, source: "ui:[data-testid=cart-badge]" }, { name: "target_2", value: 2, source: "api:/api/cart.count", call_id: "call-cart" }] : s.check === "F-1" ? [{ name: "total", value: 36.4, source: "ui:[data-testid=cart-total]" }, { name: "discount", value: 0, source: "api:/api/cart.discount", call_id: "call-cart" }] : [{ name: "status", value: f?.actual }],
    },
    evidence: {
      items: [img("annotated", "annotated"), img("screenshot_before", "before"), img("screenshot_after", "after")],
      network_calls: (ctx?.calls ?? []).map((c) => ({ id: c.id, evidence_id: `ev-${c.id}`, method: c.method, url: c.url, status: c.status, duration_ms: c.duration_ms, response_excerpt: JSON.stringify(c.response_body ?? {}), inline: { request: c.request_body, response: c.response_body } })),
      step_seq: s.step, flow_key: s.flow,
    },
    reproducibility: { seen_in: s.runs.length, of_last: 3, first_seen_run_id: s.runs[0], last_seen_run_id: s.runs[s.runs.length - 1], occurrences: s.runs.length },
    integrity: { run_id: s.runs[s.runs.length - 1], playbook_version_id: "pbv-2" },
    narrative: { status: "generated", impact: "Shoppers see a number that does not match their cart, so they may distrust the page or miss items.", suspected_cause: "The badge counts distinct lines instead of quantities (a guess based on 1 vs 2).", cited_evidence_ids: [`${s.id}-screenshot_after`] },
  };
};

export const mockLive = {
  async issues(status?: string): Promise<Issue[]> {
    const runs = await runsById();
    return SPECS.filter((s) => !status || s.status === status).map((s) => { const { occurrence_list: _o, ...rest } = toIssue(s, runs); void _o; return rest; });
  },
  async issue(id: string): Promise<IssueDetail> {
    const s = SPECS.find((x) => x.id === id);
    if (!s) throw new Error("Bug not found");
    return toIssue(s, await runsById());
  },
  async issueReport(id: string): Promise<Report> {
    const s = SPECS.find((x) => x.id === id);
    if (!s) throw new Error("No write-up yet");
    return { id: `rep-${id}`, app_id: APP, kind: "bug", issue_id: id, status: "ready", content: await issueContent(s), generated_at: new Date().toISOString() } as Report;
  },
  async runReport(runId: string): Promise<Report> {
    const ev = (await eventsFor(runId)).map((e) => e.event);
    const flows = ev.filter((e) => e.type === "flow.finished").map((e) => (e.type === "flow.finished" ? e.payload : null)!);
    const findings = ev.filter((e) => e.type === "finding").map((e) => (e.type === "finding" ? e.payload : null)!);
    const fin = ev.find((e) => e.type === "run.finished");
    const totals = fin && fin.type === "run.finished" ? fin.payload.totals : null;
    const run = await api.getRun(runId);
    const issueOf = (f: string) => SPECS.find((s) => s.finding === f)?.id ?? null;
    const byCat: Record<string, any[]> = {};
    findings.forEach((f) => { const cat = f.kind === "formula" ? "formula" : f.kind === "network" ? "network" : f.kind === "timing" ? "performance" : "ux"; (byCat[cat] ||= []).push({ id: f.id, title: f.title, severity: f.severity, flow: f.flow_key, step_seq: f.step_seq, issue_id: issueOf(f.id), requirement_keys: [], judged_by: "code" }); });
    const calls = ev.filter((e) => e.type === "network.call").map((e) => (e.type === "network.call" ? e.payload : null)!).filter((c) => c.is_api).sort((a, b) => b.duration_ms - a.duration_ms).slice(0, 5);
    return {
      id: `rep-${runId}`, app_id: APP, run_id: runId, kind: "run", status: "ready", generated_at: new Date().toISOString(),
      content: {
        kind: "run", run: { id: runId, status: run.status, mode: run.mode }, integrity: { run_id: runId, playbook_hash: "sha2c0ffee", manifest_hash: "9f2c41ab77d0" },
        summary: { flows: flows.map((f) => ({ flow_key: f.flow_key, status: f.status === "failed" ? "passed_with_findings" : f.status, step_count: 3, duration_ms: f.duration_ms, findings: findings.filter((x) => x.flow_key === f.flow_key).length, failure_reason: null })), issues: { new: 0, recurring: 3, regressed: 1, resolved: 0 }, total_findings: findings.length, duration_ms: totals ? totals.steps * 900 : 0, cost_usd: totals?.cost_usd ?? 0 },
        requirements: REQS.map((r) => ({ key: r.key, title: r.title, priority: r.priority, status: r.status === "uncovered" ? "not_covered" : r.status, covered_by: r.items, finding_ids: [] })),
        findings_by_category: byCat,
        performance: { slowest_api_calls: calls.map((c) => ({ id: c.id, method: c.method, url: c.url, duration_ms: c.duration_ms, status: c.status })), longest_waits: [{ step_id: "s1", flow: "checkout", step_seq: 3, settle_ms: 2600 }] },
        recommendations: findings.slice(0, 3).map((f, i) => ({ category: ["functional", "ux", "performance"][i % 3], text: `Fix: ${f.title}`, rationale: `The run recorded ${f.title.toLowerCase()} (expected ${f.expected}, got ${f.actual}).`, evidence_finding_ids: [f.id], requirement_keys: [], confidence: "high", effort: "m" })),
        recommendations_status: "generated", recommendations_dropped: [],
        test_quality: { escalations: totals?.escalations ?? 0, low_confidence_decisions: [{ step_id: "s3", decider: "jev", confidence: 0.58, branch: "ESCALATE" }], divergences: 0, judged_findings: 1, checks_run: 14 },
        appendix: { bug_reports: SPECS.slice(0, 4).map((s) => ({ issue_id: s.id, report_id: `rep-${s.id}` })), manifest_hash: "9f2c41ab77d0" },
      },
    } as Report;
  },
  async traceability(): Promise<Traceability> {
    return {
      version_id: "pbv-2", playbook_id: "pb-checkout", latest_run_id: "run-h3",
      requirements: REQS.map((r) => ({
        key: r.key, title: r.title, priority: r.priority, prd_ref: r.prd_ref, acceptance: r.acceptance, status: r.status,
        items: r.items.map((k) => ({ key: k, category: k.startsWith("F-") ? "formula" : k.startsWith("EC-") ? "edge_case" : k.startsWith("UX-") ? "ux_rule" : "flow", title: k, relation: "covers", latest_result: { passed: r.status !== "covered_failing" || k.startsWith("EC") || k === "UX-3" } })),
        finding_ids: r.failing.map((i) => SPECS.find((s) => s.id === i)!.finding), issue_ids: r.failing,
      })),
      uncovered: ["REQ-4"],
    } as Traceability;
  },
  async evidence(findingId: string): Promise<Evidence> {
    const ctx = await findingContext(findingId);
    if (!ctx) throw new Error("Finding not found");
    const spec = SPECS.find((s) => s.finding === findingId)!;
    const img = (kind: string, title: string) => ({ id: `${findingId}-${kind}`, kind, ref_id: `mock/${kind}`, note: "", available: true, artifact_id: null, src: shot(title, 1, ctx.step?.candidates ?? [], null) });
    const f = ctx.finding;
    return {
      finding: { id: f.id, run_id: ctx.run, flow_run_id: "fr", step_seq: f.step_seq, severity: f.severity, kind: f.kind, title: f.title, expected: f.expected, actual: f.actual, check_key: spec.check, requirement_keys: spec.reqs, fingerprint: `fp-${spec.id}`, issue_id: spec.id, judged_by: spec.judged ?? "code" },
      check_result: { check_key: spec.check, passed: false, expected: f.expected, actual: f.actual, judged_by: spec.judged ?? "code", confidence: null, inputs: Object.fromEntries(Object.entries(f.evidence).map(([k, v]) => [k, { value: v, source: "recorded" }])) },
      evidence: [img("annotated", "annotated"), img("screenshot_before", "before"), img("screenshot_after", "after"), ...ctx.calls.map((c) => ({ id: `ev-${c.id}`, kind: "network_call", ref_id: c.id, note: "", call: { id: c.id, method: c.method, url: c.url, status: c.status, duration_ms: c.duration_ms }, inline: { request: c.request_body, response: c.response_body } }))] as any,
      decisions: (ctx.step?.decisions ?? []).map((d, i) => ({ step_id: `s${i}`, decider: d.decider, choice: Number(d.choice), confidence: d.confidence, branch: d.branch, few_shot_ids: [] })),
      spans: [], integrity: { run_id: ctx.run, playbook_version_id: "pbv-2" },
    } as Evidence;
  },
  validate(md: string): Validation { return validateMarkdown(md) as unknown as Validation; },
  async extractPrd(slug: string): Promise<{ proposals: Proposal[]; markdown: string }> {
    const app = await api.getApp(slug);
    const sentences = (app.prd_markdown ?? "").split(/(?<=[.!?])\s+|\n+/).map((s) => s.replace(/^#+\s*/, "").trim()).filter((s) => /\b(must|should|can|shall|requires?)\b/i.test(s));
    const proposals = sentences.slice(0, 4).map((q, i) => ({ key: `REQ-${i + 1}`, title: q.replace(/[.!?]$/, ""), prd_ref: "Product document", acceptance: `Observable: ${q.replace(/[.!?]$/, "").toLowerCase()}.`, priority: "high", quote: q }));
    return { proposals, markdown: "" };
  },
  async normalize(raw: string): Promise<{ markdown: string; warnings: string[]; notes: string | null }> {
    const clauses = raw.split(/[.;\n]+/).map((s) => s.trim()).filter(Boolean);
    const should = clauses.filter((c) => /\b(should|must)\b/i.test(c));
    const steps = clauses.filter((c) => !should.includes(c)).map((c) => c.replace(/^(test the shop:?\s*)/i, "").replace(/^(first|then|and)\s+/i, ""));
    const md = ["# Playbook: Notes", "base_url: http://localhost:8001", "", "## Flows", "### Flow: notes", "- severity: high", "", "#### Steps",
      ...steps.map((s, i) => `${i + 1}. ${s.charAt(0).toUpperCase()}${s.slice(1)}`), "", "#### Expect", ...should.map((s) => `- ${s.replace(/^the /i, "")}`), ""].join("\n");
    return { markdown: md, warnings: [], notes: "Rewritten offline (demo mode)." };
  },
};
