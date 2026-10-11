"use client";
import { X } from "lucide-react";
import { useEffect } from "react";
import { Badge, Card, SeverityBadge, StatusPill, cn, fmtBytes, fmtMs } from "@/components/ui";
import type { Step, StepTimings } from "@/lib/api/types";
import type { RunView } from "@/lib/run-state";

/* eslint-disable @next/next/no-img-element */
const PHASES: [keyof StepTimings, string, string][] = [
  ["observe_ms", "observe", "bg-slate-400"], ["extract_ms", "extract", "bg-sky-400"], ["decide_ms", "decide", "bg-violet"],
  ["gate_ms", "gate", "bg-warn"], ["act_ms", "act", "bg-accent"], ["settle_ms", "settle", "bg-emerald-400"], ["verify_ms", "verify", "bg-ok"],
];

export function StepDrawer({ step, view, onClose }: { step: Step; view: RunView; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const calls = view.network.filter((n) => n.flow_key === step.flow_key && n.step_seq === step.seq);
  const findings = view.findings.filter((f) => f.flow_key === step.flow_key && f.step_seq === step.seq);
  const total = step.timings ? PHASES.reduce((a, [k]) => a + step.timings![k], 0) : 0;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <aside role="dialog" aria-label={`Step ${step.seq} details`} onClick={(e) => e.stopPropagation()}
        className="slide-in h-full w-full max-w-2xl space-y-5 overflow-y-auto border-l border-line bg-background p-5">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-xs text-muted">{step.flow_key} · step {step.seq} · <span className="font-mono">{step.url}</span></div>
            <h3 className="text-lg font-medium">{step.intent}</h3>
          </div>
          <StatusPill status={step.status === "running" ? "running" : step.status} />
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted hover:bg-white/10"><X className="size-5" /></button>
        </div>

        {step.screenshot && (
          <div className="relative overflow-hidden rounded-lg border border-line bg-black/30">
            <img src={step.screenshot} alt="Step screenshot" className="w-full" />
            {step.candidates.map((c) => {
              const [x, y, w, h] = c.rect;
              const chosen = c.id === step.action_id;
              return <div key={c.id} title={`#${c.id} ${c.role}: ${c.label}`} className={cn("absolute border", chosen ? "border-2 border-accent bg-accent/15" : "border-violet/60")}
                style={{ left: `${(x / 1280) * 100}%`, top: `${(y / 800) * 100}%`, width: `${(w / 1280) * 100}%`, height: `${(h / 800) * 100}%` }}>
                <span className={cn("absolute -top-2.5 left-1 rounded px-1 text-[10px] font-medium", chosen ? "bg-accent text-slate-950" : "bg-violet/80 text-white")}>{c.id}</span>
              </div>;
            })}
          </div>
        )}
        {step.wait_frames.length > 0 && (
          <Section title={`Wait frames (${step.wait_frames.length})`}>
            <div className="flex gap-2">{step.wait_frames.map((w, i) => <img key={i} src={w} alt={`Wait frame ${i + 1}`} className="h-24 rounded border border-line" />)}</div>
          </Section>
        )}

        <Section title="Decisions">
          {!step.decisions.length && <div className="text-sm text-muted">No decision yet.</div>}
          <div className="space-y-2">
            {step.decisions.map((d, i) => {
              const top = Object.entries(d.probabilities).sort((a, b) => b[1] - a[1]).slice(0, 3);
              return (
                <Card key={i} className="space-y-2 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={d.decider === "claude" ? "violet" : "accent"}>{d.decider}</Badge>
                    <span className="text-xs text-muted">{d.model_version}</span>
                    <Badge tone={d.branch === "AUTO" ? "ok" : d.branch === "ESCALATE" ? "warn" : "bad"}>{d.branch}</Badge>
                    <span className="ml-auto text-xs tabular-nums text-muted">{fmtMs(d.latency_ms)} · {d.input_tokens}→{d.output_tokens} tok</span>
                  </div>
                  <div className="text-muted">{d.question}</div>
                  {top.map(([id, p]) => {
                    const c = step.candidates.find((x) => String(x.id) === id);
                    return (
                      <div key={id} className="flex items-center gap-2 text-xs">
                        <span className="w-28 truncate">{c ? `${id} · ${c.label}` : id}</span>
                        <div className="h-1.5 flex-1 rounded-full bg-white/10"><div className={cn("h-full rounded-full", id === d.choice ? "bg-accent" : "bg-slate-500")} style={{ width: `${p * 100}%` }} /></div>
                        <span className="w-10 text-right tabular-nums">{(p * 100).toFixed(0)}%</span>
                      </div>
                    );
                  })}
                </Card>
              );
            })}
          </div>
        </Section>

        {step.timings && (
          <Section title={`Timings · ${fmtMs(total)}`}>
            <div className="flex h-3 overflow-hidden rounded-full bg-white/10">
              {PHASES.map(([k, , color]) => <div key={k} className={color} style={{ width: `${(step.timings![k] / total) * 100}%` }} title={`${k} ${step.timings![k]}ms`} />)}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              {PHASES.map(([k, label, color]) => <span key={k} className="flex items-center gap-1.5"><span className={cn("size-2 rounded-full", color)} />{label} {fmtMs(step.timings![k])}</span>)}
            </div>
          </Section>
        )}

        {step.verified.length > 0 && (
          <Section title="Verification">
            <ul className="space-y-1.5 text-sm">
              {step.verified.map((v, i) => (
                <li key={i} className="flex items-start gap-2"><Badge tone={v.passed ? "ok" : "bad"}>{v.passed ? "pass" : "fail"}</Badge><span>{v.assertion}<span className="block text-xs text-muted">{v.message}</span></span></li>
              ))}
            </ul>
          </Section>
        )}

        {findings.length > 0 && (
          <Section title="Findings">
            {findings.map((f) => (
              <Card key={f.id} className="space-y-1 border-bad/30 p-3 text-sm">
                <div className="flex items-center gap-2"><SeverityBadge severity={f.severity} /><span className="font-medium">{f.title}</span></div>
                <div className="text-xs text-muted">expected <b className="text-foreground">{f.expected}</b> · actual <b className="text-bad">{f.actual}</b></div>
              </Card>
            ))}
          </Section>
        )}

        {calls.length > 0 && (
          <Section title={`Network (${calls.length})`}>
            <ul className="space-y-1 font-mono text-xs">
              {calls.map((c) => (
                <li key={c.id} className="flex items-center gap-2">
                  <Badge tone={c.status >= 400 ? "bad" : "ok"}>{c.status}</Badge><span>{c.method}</span><span className="truncate">{c.url}</span>
                  <span className="ml-auto text-muted">{fmtMs(c.duration_ms)} · {fmtBytes(c.resp_size)}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </aside>
    </div>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2"><h4 className="text-xs font-medium uppercase tracking-wide text-muted">{title}</h4>{children}</section>
);
