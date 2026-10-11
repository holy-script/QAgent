import type {
  App, Candidate, Decision, Finding, Mode, NetworkCall, Playbook, Run, RunTotals,
  Severity, SseEnvelope, Step, Tier,
} from "./types";
import { parsePlaybook } from "../playbook-parser";

export const SAMPLE_PLAYBOOK = `# Playbook: Checkout flow
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
- cart_total: \`total == round(sum(i.price * i.qty for i in items) * (1 + tax_rate), 2)\`
  - source: both
  - bindings: items=api:/api/cart.items, total=ui:[data-testid=cart-total], tax_rate=const:0.08

### Edge cases
- Quantity set to 0
- Apply expired coupon

## Flow: checkout
Severity: critical

### Steps
1. Open /checkout
2. Fill shipping address
3. Pay with test card

### Expect
- Order confirmation is shown
`;

const iso = (minsAgo: number) => new Date(Date.now() - minsAgo * 60_000).toISOString();

export const APP_ID = "app-demo-shop";
export const seedApps = (): App[] => [
  {
    id: APP_ID,
    slug: "demo-shop",
    name: "Demo Shop",
    base_url: "http://localhost:8001",
    allowed_hosts: ["localhost", "127.0.0.1"],
    description: "FastAPI + Jinja storefront with five planted bugs.",
    prd_markdown: "",
    default_mode: "hybrid",
    gate_overrides: {},
    redact_keys: ["authorization", "cookie"],
    created_at: iso(60 * 24 * 3),
  },
];

export const seedPlaybooks = (): Playbook[] => {
  const v = (n: number, md: string) => ({
    id: `pbv-${n}`, playbook_id: "pb-checkout", version_no: n, raw_markdown: md,
    ...parsePlaybook(md), content_hash: `sha${n}c0ffee`.padEnd(12, "0"), created_at: iso(60 * 24 * (3 - n)),
  });
  const v1 = v(1, SAMPLE_PLAYBOOK.replace(/\n## Flow: checkout[\s\S]*/, "\n"));
  const v2 = v(2, SAMPLE_PLAYBOOK);
  return [{
    id: "pb-checkout", app_id: APP_ID, name: "Checkout flow", current_version_id: v2.id,
    status: "confirmed", versions: [v2, v1],
  }];
};

// ---------- screenshots (inline SVG so fixtures need no binary assets) ----------

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
function shot(title: string, badge: number, cands: Candidate[], active: number | null, extra = "") {
  const rects = cands.map((c) => {
    const [x, y, w, h] = c.rect;
    const on = c.id === active;
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${on ? "#e0f2fe" : "#f1f5f9"}" stroke="${on ? "#06b6d4" : "#cbd5e1"}" stroke-width="${on ? 4 : 2}"/>` +
      `<text x="${x + 16}" y="${y + h / 2 + 8}" font-size="22" fill="#334155" font-family="sans-serif">${esc(c.label)}</text>`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 800"><rect width="1280" height="800" fill="#fff"/>` +
    `<rect width="1280" height="72" fill="#0f172a"/><text x="32" y="46" font-size="26" fill="#fff" font-family="sans-serif" font-weight="700">Demo Shop</text>` +
    `<circle cx="1220" cy="36" r="18" fill="#f43f5e"/><text x="1220" y="44" font-size="22" fill="#fff" text-anchor="middle" font-family="sans-serif">${badge}</text>` +
    `<text x="48" y="130" font-size="34" fill="#0f172a" font-family="sans-serif" font-weight="600">${esc(title)}</text>${rects}${extra}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
const cand = (id: number, role: string, label: string, i: number): Candidate => ({
  id, role, label, rect: [48 + (i % 2) * 600, 170 + Math.floor(i / 2) * 110, 560, 80],
});

// ---------- scripted run ----------

type StepSpec = {
  flow: string; intent: string; tag: string; url: string; labels: string[]; pick: number;
  decider?: "jev" | "claude"; conf: number; badge: number; ok?: boolean;
  net?: Omit<NetworkCall, "id" | "flow_key" | "step_seq">[];
  assert: [string, boolean, string][]; settle?: number; spinner?: boolean;
};
const SPECS: StepSpec[] = [
  { flow: "add-to-cart", intent: "Open /products", tag: "products", url: "/products", labels: ["Add Mug", "Add Tee", "Add Cap", "Cart"], pick: 0, conf: 0.97, badge: 0,
    net: [{ method: "GET", url: "/api/products", status: 200, duration_ms: 42, req_size: 0, resp_size: 1840, is_api: true }],
    assert: [["Product list is visible", true, "4 products rendered"]] },
  { flow: "add-to-cart", intent: "Add 2 items to cart", tag: "products", url: "/products", labels: ["Add Mug", "Add Tee", "Add Cap", "Cart"], pick: 1, conf: 0.91, badge: 1,
    net: [{ method: "POST", url: "/api/cart", status: 200, duration_ms: 61, req_size: 28, resp_size: 212, is_api: true, request_body: { sku: "mug", qty: 1 }, response_body: { items: [{ sku: "mug", qty: 1, price: 12 }] } }],
    assert: [["Cart badge equals cart contents", false, "badge shows 1, API cart has 2 items"]] },
  { flow: "add-to-cart", intent: "Go to /cart", tag: "cart", url: "/cart", labels: ["Checkout", "Apply coupon", "Qty +", "Remove"], pick: 0, conf: 0.58, decider: "jev", badge: 1,
    net: [{ method: "GET", url: "/api/cart", status: 200, duration_ms: 38, req_size: 0, resp_size: 402, is_api: true, response_body: { items: [{ sku: "mug", qty: 1, price: 12 }, { sku: "tee", qty: 1, price: 20 }], total: 36.4 } }],
    assert: [["Total is visible", true, "$36.40"], ["cart_total formula", false, "expected 34.56, got 36.40"]] },
  { flow: "checkout", intent: "Open /checkout", tag: "checkout", url: "/checkout", labels: ["Name", "Address", "Postal code", "Pay now"], pick: 2, conf: 0.93, badge: 2,
    net: [{ method: "GET", url: "/checkout", status: 200, duration_ms: 77, req_size: 0, resp_size: 5200, is_api: false }],
    assert: [["Checkout form visible", true, "4 fields"]] },
  { flow: "checkout", intent: "Fill shipping address", tag: "checkout", url: "/checkout", labels: ["Name", "Address", "Postal code", "Pay now"], pick: 2, conf: 0.34, badge: 2, decider: "claude",
    assert: [["Postal code validated", false, "accepted 'abc' as postal code"]] },
  { flow: "checkout", intent: "Pay with test card", tag: "checkout", url: "/checkout", labels: ["Name", "Address", "Postal code", "Pay now"], pick: 3, conf: 0.88, badge: 2, settle: 2600, spinner: true,
    net: [{ method: "POST", url: "/api/pay", status: 500, duration_ms: 204, req_size: 96, resp_size: 58, is_api: true, request_body: { card: "4242…", amount: 36.4 }, response_body: { error: "upstream timeout" } }],
    assert: [["Order confirmation is shown", false, "no confirmation within settle window"]] },
];
const FINDINGS: Record<string, Omit<Finding, "id" | "flow_key" | "step_seq">> = {
  "add-to-cart:2": { severity: "medium", kind: "dom", title: "Cart badge disagrees with cart contents", expected: "badge = 2", actual: "badge = 1", evidence: { ui: "[data-testid=cart-badge]", api: "/api/cart.items.length" } },
  "add-to-cart:3": { severity: "high", kind: "formula", title: "cart_total formula violated", expected: "34.56", actual: "36.40", evidence: { formula: "total == round(sum(i.price*i.qty)*(1+tax_rate),2)", bindings: { tax_rate: 0.08 } } },
  "checkout:2": { severity: "medium", kind: "dom", title: "Postal code accepts invalid input", expected: "validation error", actual: "form accepted 'abc'", evidence: { field: "#postal" } },
  "checkout:3": { severity: "critical", kind: "network", title: "POST /api/pay returned 500", expected: "2xx", actual: "500", evidence: { call: "POST /api/pay" } },
};

const TIMINGS = (decide: number, settle = 120) => ({
  observe_ms: 35, extract_ms: 22, decide_ms: decide, gate_ms: 1, act_ms: 64, settle_ms: settle, verify_ms: 18,
});

export function buildRunEvents(run: Run, specs = SPECS): SseEnvelope[] {
  const out: SseEnvelope[] = [];
  let t = 0, seq = 0;
  const push = (event: SseEnvelope["event"], dt = 250) => { t += dt; out.push({ seq: seq++, ts: t, event }); };
  const flows = [...new Set(specs.map((s) => s.flow))];
  const sev: Record<string, Severity> = { "add-to-cart": "high", checkout: "critical" };
  const n = { jev: 0, claude: 0, esc: 0, cost: 0, steps: 0, find: 0 };
  const lat: number[] = [];
  const spanRoot = "span-run";

  push({ type: "run.started", payload: { run, flows: flows.map((key) => ({ key, severity: sev[key] ?? "medium" })) } }, 0);
  push({ type: "span", payload: { span_id: spanRoot, parent_span_id: null, name: "run", kind: "run", start_ms: 0, end_ms: 0, status: "ok", attributes: { mode: run.mode } } }, 0);

  for (const flow of flows) {
    const fStart = t;
    push({ type: "flow.started", payload: { flow_key: flow } });
    let failed: string | null = null;
    specs.filter((s) => s.flow === flow).forEach((s, i) => {
      const seq1 = i + 1;
      const cands = s.labels.map((l, k) => cand(k + 1, k === s.labels.length - 1 && l === "Cart" ? "link" : "button", l, k));
      const claude = (run.mode === "baseline") || s.decider === "claude";
      const decider: Decision["decider"] = run.mode === "stub" ? "stub" : claude ? "claude" : "jev";
      const conf = s.conf;
      const branch: Tier = conf >= 0.75 ? "AUTO" : conf >= 0.45 ? "ESCALATE" : "ESCALATE";
      const escalated = decider === "jev" && branch === "ESCALATE";
      const latency = decider === "claude" ? 1400 + seq1 * 120 : 180 + seq1 * 35;
      const chosen = cands[s.pick];
      const sStart = t;
      const step: Step = {
        flow_key: flow, seq: seq1, intent: s.intent, action_id: null, action_label: "", page_tag: s.tag, url: s.url,
        status: "running", screenshot: shot(s.tag, s.badge, cands, null), wait_frames: [], candidates: cands, decisions: [], timings: null, verified: [],
      };
      push({ type: "step.observed", payload: { step } });
      push({ type: "log", payload: { id: `l${seq}a`, flow_key: flow, step_seq: seq1, level: "debug", source: "extractor", message: `extracted ${cands.length} candidates on ${s.url}`, ts: t } }, 20);

      const probs = Object.fromEntries(cands.map((c, k) => [String(c.id), k === s.pick ? conf : (1 - conf) / (cands.length - 1)]));
      const mk = (d: Decision["decider"], c: number, ms: number, br: Tier): Decision => ({
        decider: d, model_version: d === "jev" ? "jev-1.13.0" : d === "claude" ? "claude-sonnet-4.6" : "stub-0", question: `Which action advances: "${s.intent}"?`,
        choice: String(chosen.id), probabilities: probs, confidence: c, branch: br, latency_ms: ms,
        input_tokens: d === "claude" ? 2100 : 640, output_tokens: d === "claude" ? 180 : 4,
      });
      const first = mk(decider, conf, latency, branch);
      push({ type: "step.decided", payload: { flow_key: flow, seq: seq1, decision: first, action_id: chosen.id, action_label: chosen.label } }, latency / 4);
      lat.push(latency); if (decider === "claude") n.claude++; else n.jev++;
      n.cost += decider === "claude" ? 0.0094 : 0.00006;
      if (escalated) {
        const second = mk("claude", 0.9, 1650, "AUTO");
        push({ type: "step.decided", payload: { flow_key: flow, seq: seq1, decision: second, action_id: chosen.id, action_label: chosen.label } }, 300);
        n.claude++; n.esc++; n.cost += 0.0094; lat.push(1650);
        push({ type: "log", payload: { id: `l${seq}b`, flow_key: flow, step_seq: seq1, level: "warn", source: "gate", message: `confidence ${conf} < auto_min 0.75 → escalated to claude`, ts: t } }, 10);
      }
      const settle = s.settle ?? 120;
      push({ type: "step.acted", payload: { flow_key: flow, seq: seq1, timings: TIMINGS(latency, settle), wait_frames: s.spinner ? [shot("loading…", s.badge, cands, chosen.id, '<circle cx="640" cy="500" r="40" fill="none" stroke="#06b6d4" stroke-width="8" stroke-dasharray="60 200"/>')] : [] } }, 200);
      (s.net ?? []).forEach((c, k) => {
        push({ type: "network.call", payload: { ...c, id: `n-${flow}-${seq1}-${k}`, flow_key: flow, step_seq: seq1 } }, 20);
      });
      const ok = s.assert.every((a) => a[1]);
      step.status = ok ? "ok" : "failed";
      push({ type: "step.verified", payload: { flow_key: flow, seq: seq1, status: step.status, verified: s.assert.map(([assertion, passed, message]) => ({ assertion, passed, message })) } }, 150);
      n.steps++;
      const f = FINDINGS[`${flow}:${seq1}`];
      if (f) {
        n.find++;
        push({ type: "finding", payload: { ...f, id: `f-${flow}-${seq1}`, flow_key: flow, step_seq: seq1 } }, 10);
        push({ type: "log", payload: { id: `l${seq}c`, flow_key: flow, step_seq: seq1, level: "error", source: "verify", message: f.title, ts: t } }, 5);
        if (!failed) failed = f.title;
      }
      const sEnd = t;
      push({ type: "span", payload: { span_id: `s-${flow}-${seq1}`, parent_span_id: `s-${flow}`, name: `step ${seq1}: ${s.intent}`, kind: "step", start_ms: sStart, end_ms: sEnd, status: ok ? "ok" : "error", attributes: { page: s.tag } } }, 0);
      push({ type: "span", payload: { span_id: `d-${flow}-${seq1}`, parent_span_id: `s-${flow}-${seq1}`, name: `decide (${decider})`, kind: "decide", start_ms: sStart + 50, end_ms: sStart + 50 + latency / 4, status: "ok", attributes: { confidence: conf } } }, 0);
    });
    push({ type: "span", payload: { span_id: `s-${flow}`, parent_span_id: spanRoot, name: `flow ${flow}`, kind: "flow", start_ms: fStart, end_ms: t, status: failed ? "error" : "ok", attributes: {} } }, 0);
    push({ type: "flow.finished", payload: { flow_key: flow, status: failed ? "failed" : "passed", duration_ms: t - fStart, failure_reason: failed } });
  }
  lat.sort((a, b) => a - b);
  const q = (p: number) => lat[Math.min(lat.length - 1, Math.floor(p * lat.length))] ?? 0;
  const totals: RunTotals = {
    steps: n.steps, flows: flows.length, findings: n.find, jev_decisions: n.jev, claude_decisions: n.claude,
    escalations: n.esc, cost_usd: +n.cost.toFixed(4), p50_decide_ms: q(0.5), p95_decide_ms: q(0.95),
  };
  push({ type: "span", payload: { span_id: spanRoot, parent_span_id: null, name: "run", kind: "run", start_ms: 0, end_ms: t, status: n.find ? "error" : "ok", attributes: { mode: run.mode } } }, 0);
  push({ type: "run.finished", payload: { status: n.find ? "failed" : "passed", totals, finished_at: new Date().toISOString() } });
  return out;
}

const emptyTotals: RunTotals = { steps: 0, flows: 0, findings: 0, jev_decisions: 0, claude_decisions: 0, escalations: 0, cost_usd: 0, p50_decide_ms: 0, p95_decide_ms: 0 };
export function makeRun(id: string, mode: Mode, minsAgo = 0, pbv = "pbv-2"): Run {
  return {
    id, app_id: APP_ID, playbook_version_id: pbv, playbook_name: "Checkout flow", mode, trigger: "manual", replay_of_run_id: null,
    status: "running", started_at: iso(minsAgo), finished_at: null, totals: emptyTotals,
  };
}

/** Finished runs shown in history, derived from the same script so totals are consistent. */
export function seedRuns(): Run[] {
  return ([["run-h3", "hybrid", 12], ["run-b2", "baseline", 55], ["run-h1", "hybrid", 60 * 20]] as const).map(([id, mode, ago]) => {
    const r = makeRun(id, mode, ago);
    const fin = buildRunEvents(r).at(-1)!.event;
    if (fin.type !== "run.finished") throw new Error("unreachable");
    return { ...r, status: fin.payload.status, totals: fin.payload.totals, finished_at: iso(ago - 1) };
  });
}

/** Sample in the backend's seven-category format (used when talking to the real API). */
export const SAMPLE_PLAYBOOK_V2 = `# Playbook: Checkout
base_url: http://localhost:8001

## Requirements
### REQ-1: Cart total applies the discount before tax
- prd_ref: §3.2 Pricing
- acceptance: total = (subtotal − discount) × (1 + tax_rate), rounded to 2 decimals
- priority: high

## Formulas
### F-1: cart_total
- rule: \`total == round((sum(i.price * i.qty for i in items) - discount) * (1 + tax_rate), 2)\`
- bindings: items=api:/api/cart.items, discount=api:/api/cart.discount, total=ui:[data-testid=cart-total], tax_rate=const:0.08
- verifies: REQ-1

## UX rules
### UX-1: Cart count is consistent across the app
- check: consistent_value
- targets: ui:[data-testid=cart-badge], api:/api/cart.count
- severity: medium

## Flows
### Flow: add-to-cart
- covers: REQ-1
- checks: F-1, UX-1
- severity: high

#### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart

#### Expect
- Cart shows 2 items
`;
