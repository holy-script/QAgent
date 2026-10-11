"use client";
import { MODE_INFO } from "@/lib/terms";
import { ChevronLeft, FileText, History, Pause, Play, RotateCcw, Square, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfirmDelete } from "@/components/confirm-delete";
import { useState } from "react";
import { FindingsTab } from "@/components/run/findings-tab";
import { FlowsTab } from "@/components/run/flows-tab";
import { GraphTab } from "@/components/run/graph-tab";
import { LogsTab } from "@/components/run/logs-tab";
import { NetworkTab } from "@/components/run/network-tab";
import { StepDrawer } from "@/components/run/step-drawer";
import { TraceTab } from "@/components/run/trace-tab";
import { Badge, Button, ErrorState, Loading, Metric, StateTabs, StatusPill, fmtMs, fmtUsd } from "@/components/ui";
import { ReplayPanel } from "@/components/live/replay-panel";
import { api, USE_MOCK } from "@/lib/api/client";
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
  const [tapePanel, setTapePanel] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const router = useRouter();
  const del = useMutation({ mutationFn: () => api.deleteRun(run.id), onSuccess: () => { toast.success("Run deleted"); router.replace(`/apps/${slug}/runs`); } });
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
        <Link href={`/apps/${slug}/runs`} className="text-muted-foreground hover:text-foreground" aria-label="Back to all runs"><ChevronLeft className="size-5" /></Link>
        <h2 className="text-lg font-medium">{live.playbook_name}</h2>
        <StatusPill status={view.done ? live.status : "running"} />
        <Badge tone={live.mode === "hybrid" ? "violet" : "neutral"}>{MODE_INFO[live.mode].label} mode</Badge>
        <span className="font-mono text-xs text-muted-foreground">{live.id}</span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {running && (
            <>
              <Button onClick={togglePause} aria-label={paused ? "Resume" : "Pause"}>{paused ? <Play className="size-4" /> : <Pause className="size-4" />}{paused ? "Resume" : "Pause"}</Button>
              <div className="flex overflow-hidden rounded-lg border border-border" role="group" aria-label="Playback speed">
                {SPEEDS.map((s) => (
                  <button key={s} onClick={() => setSpeed(s)} aria-pressed={speed === s}
                    className={`px-2.5 py-2 text-xs tabular-nums ${speed === s ? "bg-brand/20 text-brand" : "text-muted-foreground hover:bg-foreground/5"}`}>{s}×</button>
                ))}
              </div>
              <Button variant="danger" onClick={() => api.stopRun(live.id)}><Square className="size-4" />Stop run</Button>
            </>
          )}
          {!running && !USE_MOCK && <Link href={`/apps/${slug}/runs/${live.id}/report`} className="inline-flex items-center gap-2 rounded-lg border border-brand/40 bg-brand/10 px-3.5 py-2 text-sm font-medium text-brand hover:bg-brand/15"><FileText className="size-4" />View report</Link>}
          {!running && !USE_MOCK && <Button onClick={() => setTapePanel((v) => !v)} aria-expanded={tapePanel}><History className="size-4" />Repeat exactly</Button>}
          {!running && <Button variant="danger" onClick={() => setConfirmDelete(true)}><Trash2 className="size-4" />Delete run</Button>}
          {!running && <Button onClick={onReplay}><RotateCcw className="size-4" />Watch again</Button>}
        </div>
      </div>

      {tapePanel && !USE_MOCK && <ReplayPanel slug={slug} runId={live.id} onClose={() => setTapePanel(false)} />}

      {running && progress.n > 0 && (
        <div className="h-1 overflow-hidden rounded-full bg-foreground/10"><div className="h-full bg-brand transition-all" style={{ width: `${(progress.i / progress.n) * 100}%` }} /></div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric label="Steps taken" info="A step is one action, such as opening a page or clicking a button." value={steps.length || t.steps} hint={`${view.flows.length} journeys`} />
        <Metric label="Problems found" info="Checks that failed in this run." value={view.findings.length} tone={view.findings.length ? "bad" : "ok"} />
        <Metric label="Fast AI / Strong AI" info="How many decisions each AI made. The fast AI handles most steps; the strong AI is asked when the fast one is unsure." value={`${jev} / ${claude}`} hint={`${steps.filter((s) => s.decisions.length > 1).length} double-checked`} />
        <Metric label="AI speed" info="Average time the AI took to choose an action." value={avg ? fmtMs(avg) : "–"} hint={t.p95_decide_ms ? `p95 ${fmtMs(t.p95_decide_ms)}` : undefined} />
        <Metric label="AI cost (estimate)" info="Approximate spend on AI calls for this run." value={fmtUsd(view.done ? t.cost_usd : cost)} />
        <Metric label="Server calls" info="Requests the app made to its server while being tested." value={view.network.length} hint={`${view.network.filter((n) => n.status >= 400).length} failed`} tone={view.network.some((n) => n.status >= 400) ? "bad" : undefined} />
      </div>

      <StateTabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "flows", label: "Journeys", count: view.flows.length },
        { id: "graph", label: "How it decided" },
        { id: "network", label: "Server calls", count: view.network.length },
        { id: "trace", label: "Timeline", count: view.spans.length },
        { id: "logs", label: "Activity", count: view.logs.length },
        { id: "findings", label: "Problems", count: view.findings.length },
      ]} />

      {tab === "flows" && <FlowsTab view={view} onOpen={open} selected={sel} />}
      {tab === "graph" && <GraphTab view={view} running={running} />}
      {tab === "network" && <NetworkTab view={view} onOpen={open} />}
      {tab === "trace" && <TraceTab view={view} />}
      {tab === "logs" && <LogsTab view={view} live={running} onOpen={open} />}
      {tab === "findings" && <FindingsTab view={view} onOpen={open} slug={slug} />}

      <ConfirmDelete open={confirmDelete} onOpenChange={setConfirmDelete} title="Delete this run?" actionLabel="Delete run" pending={del.isPending} error={del.error?.message} onConfirm={() => del.mutate()}>
        <p>The run, its screenshots, proof and report are removed. Bugs that only this run found disappear too.</p>
      </ConfirmDelete>

      {selStep && <StepDrawer step={selStep} view={view} runId={run.id} onClose={() => setSel(null)} />}
    </div>
  );
}
