"use client";
import { useState } from "react";
import { Minus, Plus } from "lucide-react";
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
  const res = await fetch(assetUrl(url), { credentials: "include" });
  if (!res.ok) return [];
  const raw = (await res.json()) as { id: number; tag: string; label: string; bounding_box?: { x: number; y: number; width: number; height: number } | null }[];
  return raw.filter((c) => c.bounding_box).map((c) => ({ id: c.id, role: c.tag, label: c.label, rect: [c.bounding_box!.x, c.bounding_box!.y, c.bounding_box!.width, c.bounding_box!.height] }));
}

export function StepDrawer({ step, view, onClose, runId }: { step: Step; view: RunView; onClose: () => void; runId: string }) {
  const live = !USE_MOCK;
  const { data: arts } = useStepArtifacts(runId, step.flow_key, step.seq, live && step.status !== "running");
  const [picked, setSide] = useState<"after" | "before" | null>(null);
  const [zoom, setZoom] = useState(1);
  const zoomTo = (z: number) => setZoom(Math.min(4, Math.max(1, Math.round(z * 4) / 4)));
  const candUrl = arts?.find((a) => a.kind === "candidates")?.url;
  const { data: liveCandidates } = useQuery({ queryKey: ["candidates", candUrl], enabled: !!candUrl, queryFn: () => loadCandidates(candUrl!) });
  const candidates = step.candidates.length ? step.candidates : (liveCandidates ?? []);
  const beforeUrl = arts?.find((a) => a.kind === "screenshot_before")?.url;
  const waitUrls = step.wait_frames.length ? step.wait_frames : (arts?.filter((a) => a.kind === "wait_frame").map((a) => assetUrl(a.url)) ?? []);
  // The boxes were measured on the page BEFORE the action, so they belong on the Before picture only; open on it when there are boxes.
  const side = picked ?? (beforeUrl && candidates.length ? "before" : "after");
  const shown = side === "before" && beforeUrl ? assetUrl(beforeUrl) : step.screenshot;
  const showBoxes = side === "before" || !beforeUrl;

  const calls = view.network.filter((n) => n.flow_key === step.flow_key && n.step_seq === step.seq);
  const findings = view.findings.filter((f) => f.flow_key === step.flow_key && f.step_seq === step.seq);
  const total = step.timings ? PHASES.reduce((a, [k]) => a + step.timings![k], 0) : 0;

  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="bottom" aria-label={`Step ${step.seq} details`}
        className="gap-0 overflow-hidden rounded-t-2xl p-0 duration-300 data-[side=bottom]:h-[94vh] data-[side=bottom]:data-ending-style:translate-y-full data-[side=bottom]:data-starting-style:translate-y-full">
        <div className="flex items-start gap-3 border-b border-border px-6 py-4 pr-14">
          <div className="min-w-0 flex-1">
            <SheetDescription className="truncate text-xs">{step.flow_key} · step {step.seq} · <span className="font-mono">{step.url}</span></SheetDescription>
            <SheetTitle className="text-xl font-medium">{step.intent}</SheetTitle>
          </div>
          <StatusPill status={step.status === "running" ? "running" : step.status} />
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 overflow-y-auto lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:overflow-hidden">
        <div className="flex min-h-0 flex-col gap-3 border-border p-5 lg:border-r">
          <div className="flex flex-wrap items-center gap-2">
            {live && beforeUrl && (
              <div className="flex gap-1" role="group" aria-label="Screenshot">
                {(["before", "after"] as const).map((k) => (
                  <button key={k} onClick={() => setSide(k)} aria-pressed={side === k}
                    className={cn("rounded-md border px-2.5 py-1 text-xs capitalize", side === k ? "border-brand bg-brand/10 text-brand" : "border-border text-muted-foreground hover:bg-secondary")}>{k}</button>
                ))}
              </div>
            )}
            {shown && (
              <div className="ml-auto flex items-center gap-1" role="group" aria-label="Zoom">
                <button onClick={() => zoomTo(zoom - 0.5)} disabled={zoom <= 1} aria-label="Zoom out" className="rounded-md border border-border p-1.5 text-muted-foreground hover:bg-secondary disabled:opacity-40"><Minus className="size-3.5" /></button>
                <button onClick={() => setZoom(1)} aria-label="Fit to width" className="w-14 rounded-md border border-border py-1 text-xs tabular-nums hover:bg-secondary">{zoom === 1 ? "Fit" : `${Math.round(zoom * 100)}%`}</button>
                <button onClick={() => zoomTo(zoom + 0.5)} disabled={zoom >= 4} aria-label="Zoom in" className="rounded-md border border-border p-1.5 text-muted-foreground hover:bg-secondary disabled:opacity-40"><Plus className="size-3.5" /></button>
              </div>
            )}
          </div>
          {showBoxes && candidates.length > 0 && <p className="text-xs text-muted-foreground">Boxes mark the buttons and links the AI could choose from. The highlighted one was used. Click the image to zoom, scroll to move around.</p>}
          {shown && (
            <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-muted">
              <div className="relative" style={{ width: `${zoom * 100}%` }}>
                <img src={shown} alt="Step screenshot" className={cn("w-full", zoom < 4 ? "cursor-zoom-in" : "cursor-zoom-out")} onClick={() => zoomTo(zoom < 4 ? zoom + 1 : 1)} />
                {showBoxes && candidates.map((c) => {
                  const [x, y, w, h] = c.rect;
                  const chosen = c.id === step.action_id;
                  return <div key={c.id} title={`#${c.id} ${c.role}: ${c.label}`} className={cn("pointer-events-none absolute border", chosen ? "border-2 border-brand bg-brand/15" : "border-violet/60")}
                    style={{ left: `${(x / 1280) * 100}%`, top: `${(y / 800) * 100}%`, width: `${(w / 1280) * 100}%`, height: `${(h / 800) * 100}%` }}>
                    <span className={cn("absolute -top-2.5 left-1 rounded px-1 text-[10px] font-medium", chosen ? "bg-brand text-primary-foreground" : "bg-violet/80 text-white")}>{c.id}</span>
                  </div>;
                })}
              </div>
            </div>
          )}
          {waitUrls.length > 0 && (
            <Section title={`While waiting (${waitUrls.length} snapshots)`}>
              <div className="flex gap-2 overflow-x-auto">{waitUrls.map((w, i) => <img key={i} src={w} alt={`Wait frame ${i + 1}`} className="h-24 rounded border border-border" />)}</div>
            </Section>
          )}
        </div>

        <div className="min-h-0 space-y-5 p-5 lg:overflow-y-auto">
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
        </div>
      </SheetContent>
    </Sheet>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2"><h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h4>{children}</section>
);
