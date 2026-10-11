"use client";
import { Check, X } from "lucide-react";
import { Card, Empty, SeverityBadge, StatusPill, cn, fmtMs } from "@/components/ui";
import type { RunView } from "@/lib/run-state";
import type { Step } from "@/lib/api/types";

/* eslint-disable @next/next/no-img-element */
export function FlowsTab({ view, onOpen, selected }: { view: RunView; onOpen: (flow: string, seq: number) => void; selected: { flow: string; seq: number } | null }) {
  if (!view.flows.length) return <Empty title="Waiting for the run to start…" />;
  return (
    <div className="space-y-4">
      {view.flows.map((f) => (
        <Card key={f.flow_key} className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-medium">{f.flow_key}</span>
            <SeverityBadge severity={f.severity} />
            <StatusPill status={f.status} />
            {f.duration_ms > 0 && <span className="text-xs text-muted tabular-nums">{fmtMs(f.duration_ms)}</span>}
            {f.failure_reason && <span className="truncate text-xs text-bad">{f.failure_reason}</span>}
          </div>
          {f.steps.length === 0 ? (
            <div className="mt-3 text-sm text-muted">{f.status === "pending" ? "Queued behind earlier flows." : "Starting…"}</div>
          ) : (
            <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
              {f.steps.map((s) => <StepThumb key={s.seq} s={s} on={selected?.flow === s.flow_key && selected.seq === s.seq} onClick={() => onOpen(s.flow_key, s.seq)} />)}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function StepThumb({ s, on, onClick }: { s: Step; on: boolean; onClick: () => void }) {
  const ring = s.status === "failed" ? "border-bad/60" : s.status === "ok" ? "border-ok/40" : "border-accent pulse-ring";
  const last = s.decisions.at(-1);
  return (
    <button onClick={onClick} className={cn("slide-in w-56 shrink-0 overflow-hidden rounded-lg border bg-surface-2 text-left transition hover:brightness-125", ring, on && "ring-2 ring-accent")}>
      <div className="relative aspect-[8/5] bg-black/30">
        {s.screenshot && <img src={s.screenshot} alt={`Step ${s.seq}: ${s.intent}`} className="size-full object-cover" loading="lazy" />}
        <span className="absolute left-1.5 top-1.5 rounded bg-black/70 px-1.5 text-[11px] tabular-nums">#{s.seq}</span>
        <span className="absolute right-1.5 top-1.5">
          {s.status === "ok" && <Check className="size-4 rounded-full bg-ok p-0.5 text-slate-950" />}
          {s.status === "failed" && <X className="size-4 rounded-full bg-bad p-0.5 text-slate-950" />}
        </span>
      </div>
      <div className="space-y-0.5 p-2.5">
        <div className="truncate text-sm">{s.intent}</div>
        <div className="flex items-center justify-between text-xs text-muted">
          <span className="truncate">{s.action_label ? `→ ${s.action_label}` : "observing…"}</span>
          {last && <span className={cn("tabular-nums", last.decider === "claude" ? "text-violet" : "text-accent")}>{last.decider} {(last.confidence * 100).toFixed(0)}%</span>}
        </div>
      </div>
    </button>
  );
}
