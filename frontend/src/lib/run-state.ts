import type { Finding, FlowRun, LogEntry, NetworkCall, Run, RunEvent, Span, Step } from "./api/types";

export interface RunView {
  run: Run | null;
  flows: FlowRun[];
  findings: Finding[];
  network: NetworkCall[];
  spans: Span[];
  logs: LogEntry[];
  done: boolean;
}
export const emptyView: RunView = { run: null, flows: [], findings: [], network: [], spans: [], logs: [], done: false };

const patchStep = (v: RunView, flow: string, seq: number, f: (s: Step) => Step): RunView => ({
  ...v,
  flows: v.flows.map((fl) => fl.flow_key !== flow ? fl : { ...fl, steps: fl.steps.map((s) => (s.seq === seq ? f(s) : s)) }),
});

export function reduce(v: RunView, e: RunEvent): RunView {
  switch (e.type) {
    case "run.started":
      return { ...emptyView, run: e.payload.run, flows: e.payload.flows.map((f) => ({ flow_key: f.key, severity: f.severity, status: "pending", duration_ms: 0, failure_reason: null, steps: [] })) };
    case "flow.started":
      return { ...v, flows: v.flows.map((f) => (f.flow_key === e.payload.flow_key ? { ...f, status: "running" } : f)) };
    case "step.observed": {
      const s = e.payload.step;
      return { ...v, flows: v.flows.map((f) => (f.flow_key === s.flow_key ? { ...f, steps: [...f.steps.filter((x) => x.seq !== s.seq), s] } : f)) };
    }
    case "step.decided": {
      const p = e.payload;
      return patchStep(v, p.flow_key, p.seq, (s) => ({ ...s, action_id: p.action_id, action_label: p.action_label, decisions: [...s.decisions, p.decision] }));
    }
    case "step.acted":
      return patchStep(v, e.payload.flow_key, e.payload.seq, (s) => ({ ...s, timings: e.payload.timings, wait_frames: e.payload.wait_frames }));
    case "step.verified":
      return patchStep(v, e.payload.flow_key, e.payload.seq, (s) => ({ ...s, status: e.payload.status, verified: e.payload.verified }));
    case "network.call": return { ...v, network: [...v.network, e.payload] };
    case "span": return { ...v, spans: [...v.spans.filter((s) => s.span_id !== e.payload.span_id), e.payload] };
    case "log": return { ...v, logs: [...v.logs, e.payload] };
    case "finding": return { ...v, findings: [...v.findings, e.payload] };
    case "flow.finished": {
      const p = e.payload;
      return { ...v, flows: v.flows.map((f) => (f.flow_key === p.flow_key ? { ...f, status: p.status, duration_ms: p.duration_ms, failure_reason: p.failure_reason } : f)) };
    }
    case "run.finished":
      return { ...v, done: true, run: v.run && { ...v.run, status: e.payload.status, totals: e.payload.totals, finished_at: e.payload.finished_at } };
  }
}

/** The step the agent is on right now (last observed, not yet verified), for the live banner and graph pulse. */
export function activeStep(v: RunView): Step | null {
  for (const f of v.flows) if (f.status === "running") return f.steps.at(-1) ?? null;
  return null;
}
