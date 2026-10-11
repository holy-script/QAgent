"use client";
import { ChevronLeft, Pause, Play, RotateCcw, Square } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { FindingsTab } from "@/components/run/findings-tab";
import { FlowsTab } from "@/components/run/flows-tab";
import { GraphTab } from "@/components/run/graph-tab";
import { LogsTab } from "@/components/run/logs-tab";
import { NetworkTab } from "@/components/run/network-tab";
import { StepDrawer } from "@/components/run/step-drawer";
import { TraceTab } from "@/components/run/trace-tab";
import { Badge, Button, ErrorState, Loading, Metric, StateTabs, StatusPill, fmtMs, fmtUsd } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useRun } from "@/lib/api/hooks";
import type { Run } from "@/lib/api/types";
import { SPEEDS, useRunStream } from "@/lib/use-run-stream";

type Tab = "flows" | "graph" | "network" | "trace" | "logs" | "findings";

export default function RunPage() {
  const { slug, runId } = useParams<{ slug: string; runId: string }>();
  const { data: run, error, isPending, refetch } = useRun(runId);
  const [replayKey, setReplayKey] = useState(0);
  if (isPending) return <Loading label="Loading run…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  // A new key remounts the body, which starts a fresh event stream (see useRunStream).
  return <RunBody key={`${run.id}:${replayKey}`} slug={slug} run={run} replay={replayKey > 0} onReplay={() => setReplayKey((k) => k + 1)} />;
}

function RunBody({ slug, run, replay, onReplay }: { slug: string; run: Run; replay: boolean; onReplay: () => void }) {
  const { view, speed, setSpeed, paused, togglePause, progress } = useRunStream(run, replay);
  // Deep links: ?tab=graph&step=checkout:3
  const q = useSearchParams();
  const [tab, setTab] = useState<Tab>((q.get("tab") as Tab) || "flows");
  const [sel, setSel] = useState<{ flow: string; seq: number } | null>(() => {
    const [flow, seq] = (q.get("step") ?? "").split(":");
    return flow && seq ? { flow, seq: Number(seq) } : null;
  });

  const live = view.run ?? run;
  const running = !view.done && (live.status === "running" || replay || progress.i < progress.n);
  const t = live.totals;
  const steps = view.flows.flatMap((f) => f.steps);
  const decisions = steps.flatMap((s) => s.decisions);
  const jev = decisions.filter((d) => d.decider !== "claude").length;
  const claude = decisions.length - jev;
  const cost = decisions.reduce((a, d) => a + (d.decider === "claude" ? 0.0094 : 0.00006), 0);
  const avg = decisions.length ? decisions.reduce((a, d) => a + d.latency_ms, 0) / decisions.length : 0;
  const selStep = sel && view.flows.find((f) => f.flow_key === sel.flow)?.steps.find((s) => s.seq === sel.seq);
  const open = (flow: string, seq: number) => setSel({ flow, seq });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link href={`/apps/${slug}/runs`} className="text-muted hover:text-foreground" aria-label="Back to runs"><ChevronLeft className="size-5" /></Link>
        <h2 className="text-lg font-medium">{live.playbook_name}</h2>
        <StatusPill status={view.done ? live.status : "running"} />
        <Badge tone={live.mode === "hybrid" ? "violet" : "neutral"}>{live.mode}</Badge>
        <span className="font-mono text-xs text-muted">{live.id}</span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {running && (
            <>
              <Button onClick={togglePause} aria-label={paused ? "Resume" : "Pause"}>{paused ? <Play className="size-4" /> : <Pause className="size-4" />}{paused ? "Resume" : "Pause"}</Button>
              <div className="flex overflow-hidden rounded-lg border border-line" role="group" aria-label="Playback speed">
                {SPEEDS.map((s) => (
                  <button key={s} onClick={() => setSpeed(s)} aria-pressed={speed === s}
                    className={`px-2.5 py-2 text-xs tabular-nums ${speed === s ? "bg-accent/20 text-accent" : "text-muted hover:bg-white/5"}`}>{s}×</button>
                ))}
              </div>
              <Button variant="danger" onClick={() => api.stopRun(live.id)}><Square className="size-4" />Stop</Button>
            </>
          )}
          {!running && <Button onClick={onReplay}><RotateCcw className="size-4" />Replay</Button>}
        </div>
      </div>

      {running && progress.n > 0 && (
        <div className="h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-accent transition-all" style={{ width: `${(progress.i / progress.n) * 100}%` }} /></div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric label="Steps" value={steps.length || t.steps} hint={`${view.flows.length} flows`} />
        <Metric label="Findings" value={view.findings.length} tone={view.findings.length ? "bad" : "ok"} />
        <Metric label="Jev / Claude" value={`${jev} / ${claude}`} hint={`${steps.filter((s) => s.decisions.length > 1).length} escalations`} />
        <Metric label="Avg decide" value={avg ? fmtMs(avg) : "–"} hint={t.p95_decide_ms ? `p95 ${fmtMs(t.p95_decide_ms)}` : undefined} />
        <Metric label="Est. cost" value={fmtUsd(view.done ? t.cost_usd : cost)} />
        <Metric label="Network" value={view.network.length} hint={`${view.network.filter((n) => n.status >= 400).length} failed`} tone={view.network.some((n) => n.status >= 400) ? "bad" : undefined} />
      </div>

      <StateTabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "flows", label: "Flows", count: view.flows.length },
        { id: "graph", label: "Graph" },
        { id: "network", label: "Network", count: view.network.length },
        { id: "trace", label: "Trace", count: view.spans.length },
        { id: "logs", label: "Logs", count: view.logs.length },
        { id: "findings", label: "Findings", count: view.findings.length },
      ]} />

      {tab === "flows" && <FlowsTab view={view} onOpen={open} selected={sel} />}
      {tab === "graph" && <GraphTab view={view} running={running} />}
      {tab === "network" && <NetworkTab view={view} onOpen={open} />}
      {tab === "trace" && <TraceTab view={view} />}
      {tab === "logs" && <LogsTab view={view} live={running} onOpen={open} />}
      {tab === "findings" && <FindingsTab view={view} onOpen={open} />}

      {selStep && <StepDrawer step={selStep} view={view} onClose={() => setSel(null)} />}
    </div>
  );
}
