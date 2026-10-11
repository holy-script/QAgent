"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Badge, Card, SeverityBadge, StatusPill, cn, fmtBytes, fmtMs } from "@/components/ui";
import { USE_MOCK } from "@/lib/api/client";
import { assetUrl, useStepArtifacts } from "@/lib/api/live";
import type { Candidate, Step, StepTimings } from "@/lib/api/types";
import type { RunView } from "@/lib/run-state";

/* eslint-disable @next/next/no-img-element */
const PHASES: [keyof StepTimings, string, string][] = [
  ["observe_ms", "observe", "bg-muted-foreground"], ["extract_ms", "extract", "bg-brand"], ["decide_ms", "decide", "bg-violet"],
  ["gate_ms", "gate", "bg-warn"], ["act_ms", "act", "bg-brand"], ["settle_ms", "settle", "bg-ok"], ["verify_ms", "verify", "bg-ok"],
];

/** Candidates the decider saw, from the stored candidates.json (backend shape -> overlay rects). */
async function loadCandidates(url: string): Promise<Candidate[]> {
  const res = await fetch(assetUrl(url));
  if (!res.ok) return [];
  const raw = (await res.json()) as { id: number; tag: string; label: string; bounding_box?: { x: number; y: number; width: number; height: number } | null }[];
  return raw.filter((c) => c.bounding_box).map((c) => ({ id: c.id, role: c.tag, label: c.label, rect: [c.bounding_box!.x, c.bounding_box!.y, c.bounding_box!.width, c.bounding_box!.height] }));
}

export function StepDrawer({ step, view, onClose, runId }: { step: Step; view: RunView; onClose: () => void; runId: string }) {
  const live = !USE_MOCK;
  const { data: arts } = useStepArtifacts(runId, step.flow_key, step.seq, live && step.status !== "running");
  const [side, setSide] = useState<"after" | "before">("after");
  const candUrl = arts?.find((a) => a.kind === "candidates")?.url;
  const { data: liveCandidates } = useQuery({ queryKey: ["candidates", candUrl], enabled: !!candUrl, queryFn: () => loadCandidates(candUrl!) });
  const candidates = step.candidates.length ? step.candidates : (liveCandidates ?? []);
  const beforeUrl = arts?.find((a) => a.kind === "screenshot_before")?.url;
  const waitUrls = step.wait_frames.length ? step.wait_frames : (arts?.filter((a) => a.kind === "wait_frame").map((a) => assetUrl(a.url)) ?? []);
  const shown = side === "before" && beforeUrl ? assetUrl(beforeUrl) : step.screenshot;

  const calls = view.network.filter((n) => n.flow_key === step.flow_key && n.step_seq === step.seq);
  const findings = view.findings.filter((f) => f.flow_key === step.flow_key && f.step_seq === step.seq);
  const total = step.timings ? PHASES.reduce((a, [k]) => a + step.timings![k], 0) : 0;

  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" aria-label={`Step ${step.seq} details`} className="w-full gap-0 overflow-y-auto p-5 sm:max-w-2xl">
        <div className="space-y-5">
        <div className="flex items-start gap-3 pr-8">
          <div className="min-w-0 flex-1">
            <SheetDescription className="text-xs">{step.flow_key} · step {step.seq} · <span className="font-mono">{step.url}</span></SheetDescription>
            <SheetTitle className="text-lg font-medium">{step.intent}</SheetTitle>
          </div>
          <StatusPill status={step.status === "running" ? "running" : step.status} />
        </div>

        {live && beforeUrl && (
          <div className="flex gap-1" role="group" aria-label="Screenshot">
            {(["before", "after"] as const).map((k) => (
              <button key={k} onClick={() => setSide(k)} aria-pressed={side === k}
                className={cn("rounded-md border px-2.5 py-1 text-xs capitalize", side === k ? "border-brand bg-brand/10 text-brand" : "border-border text-muted-foreground hover:bg-foreground/5")}>{k}</button>
            ))}
          </div>
        )}
        {candidates.length > 0 && <p className="text-xs text-muted-foreground">Boxes mark the buttons and links the AI could choose from. The highlighted one was used.</p>}
        {shown && (
          <div className="relative overflow-hidden rounded-lg border border-border bg-muted">
            <img src={shown} alt="Step screenshot" className="w-full" />
            {candidates.map((c) => {
              const [x, y, w, h] = c.rect;
              const chosen = c.id === step.action_id;
              return <div key={c.id} title={`#${c.id} ${c.role}: ${c.label}`} className={cn("absolute border", chosen ? "border-2 border-brand bg-brand/15" : "border-violet/60")}
                style={{ left: `${(x / 1280) * 100}%`, top: `${(y / 800) * 100}%`, width: `${(w / 1280) * 100}%`, height: `${(h / 800) * 100}%` }}>
                <span className={cn("absolute -top-2.5 left-1 rounded px-1 text-[10px] font-medium", chosen ? "bg-brand text-primary-foreground" : "bg-violet/80 text-white")}>{c.id}</span>
              </div>;
            })}
          </div>
        )}
        {waitUrls.length > 0 && (
          <Section title={`While waiting (${waitUrls.length} snapshots)`}>
            <div className="flex gap-2 overflow-x-auto">{waitUrls.map((w, i) => <img key={i} src={w} alt={`Wait frame ${i + 1}`} className="h-24 rounded border border-border" />)}</div>
          </Section>
        )}

        <Section title="What the AI chose">
          {!step.decisions.length && <div className="text-sm text-muted-foreground">No AI choice was needed for this step (for example, opening a page).</div>}
          <div className="space-y-2">
            {step.decisions.map((d, i) => {
              const top = Object.entries(d.probabilities).sort((a, b) => b[1] - a[1]).slice(0, 3);
              return (
                <Card key={i} className="space-y-2 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={d.decider === "claude" ? "violet" : "accent"}>{d.decider}</Badge>
                    <span className="text-xs text-muted-foreground">{d.model_version}</span>
                    <Badge tone={d.branch === "AUTO" ? "ok" : d.branch === "ESCALATE" ? "warn" : "bad"}>{d.branch === "AUTO" ? "Acted on its own" : d.branch === "ESCALATE" ? "Double-checked" : "Stopped"}</Badge>
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{fmtMs(d.latency_ms)} · {d.input_tokens + d.output_tokens} tokens</span>
                  </div>
                  <div className="text-muted-foreground">{d.question}</div>
                  {top.map(([id, p]) => {
                    const c = candidates.find((x) => String(x.id) === id);
                    return (
                      <div key={id} className="flex items-center gap-2 text-xs">
                        <span className="w-28 truncate">{c ? `${id} · ${c.label}` : id}</span>
                        <div className="h-1.5 flex-1 rounded-full bg-foreground/10"><div className={cn("h-full rounded-full", id === d.choice ? "bg-brand" : "bg-muted-foreground")} style={{ width: `${p * 100}%` }} /></div>
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
          <Section title={`Where the time went · ${fmtMs(total)}`}>
            <div className="flex h-3 overflow-hidden rounded-full bg-foreground/10">
              {PHASES.map(([k, , color]) => <div key={k} className={color} style={{ width: `${(step.timings![k] / total) * 100}%` }} title={`${k} ${step.timings![k]}ms`} />)}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {PHASES.map(([k, label, color]) => <span key={k} className="flex items-center gap-1.5"><span className={cn("size-2 rounded-full", color)} />{label} {fmtMs(step.timings![k])}</span>)}
            </div>
          </Section>
        )}

        {step.verified.length > 0 && (
          <Section title="Checks">
            <ul className="space-y-1.5 text-sm">
              {step.verified.map((v, i) => (
                <li key={i} className="flex items-start gap-2"><Badge tone={v.passed ? "ok" : "bad"}>{v.passed ? "pass" : "fail"}</Badge><span>{v.assertion}<span className="block text-xs text-muted-foreground">{v.message}</span></span></li>
              ))}
            </ul>
          </Section>
        )}

        {findings.length > 0 && (
          <Section title="Problems found at this step">
            {findings.map((f) => (
              <Card key={f.id} className="space-y-1 border-bad/30 p-3 text-sm">
                <div className="flex items-center gap-2"><SeverityBadge severity={f.severity} /><span className="font-medium">{f.title}</span></div>
                <div className="text-xs text-muted-foreground">should be <b className="text-foreground">{f.expected}</b> · was <b className="text-bad">{f.actual}</b></div>
              </Card>
            ))}
          </Section>
        )}

        {calls.length > 0 && (
          <Section title={`Server calls (${calls.length})`}>
            <ul className="space-y-1 font-mono text-xs">
              {calls.map((c) => (
                <li key={c.id} className="flex items-center gap-2">
                  <Badge tone={c.status >= 400 ? "bad" : "ok"}>{c.status}</Badge><span>{c.method}</span><span className="truncate">{c.url}</span>
                  <span className="ml-auto text-muted-foreground">{fmtMs(c.duration_ms)} · {fmtBytes(c.resp_size)}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2"><h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h4>{children}</section>
);
