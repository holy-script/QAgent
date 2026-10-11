"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Card, Empty, ErrorState, Loading, cn, fmtMs, fmtUsd } from "@/components/ui";
import { useRuns } from "@/lib/api/hooks";
import type { Run } from "@/lib/api/types";

// Lower is better for every metric here; the winner gets the green bar.
const METRICS: { label: string; get: (r: Run) => number; fmt: (n: number) => string }[] = [
  { label: "Findings", get: (r) => r.totals.findings, fmt: String },
  { label: "Cost", get: (r) => r.totals.cost_usd, fmt: fmtUsd },
  { label: "p50 decide", get: (r) => r.totals.p50_decide_ms, fmt: fmtMs },
  { label: "p95 decide", get: (r) => r.totals.p95_decide_ms, fmt: fmtMs },
  { label: "Claude calls", get: (r) => r.totals.claude_decisions, fmt: String },
  { label: "Escalations", get: (r) => r.totals.escalations, fmt: String },
];

function RunSelect({ value, onChange, label, runs }: { value: string; onChange: (v: string) => void; label: string; runs: Run[] }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
      {runs.map((r) => <option key={r.id} value={r.id}>{r.mode} · {r.id.slice(0, 10)} · {r.playbook_name}</option>)}
    </select>
  );
}

export default function Compare() {
  const { slug } = useParams<{ slug: string }>();
  const { data, error, isPending, refetch } = useRuns(slug);
  const [pick, setPick] = useState<{ a?: string; b?: string }>({});
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  const done = data.filter((r) => r.status !== "running");
  const a = done.find((r) => r.id === pick.a) ?? done.find((r) => r.mode === "hybrid");
  const b = done.find((r) => r.id === pick.b) ?? done.find((r) => r.mode === "baseline");
  if (!a || !b || a.id === b.id) return <Empty title="Need two finished runs to compare" hint="Run the same playbook in hybrid and baseline mode, then come back." />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <RunSelect runs={done} label="Run A" value={a.id} onChange={(v) => setPick({ ...pick, a: v })} />
        <span className="text-muted">vs</span>
        <RunSelect runs={done} label="Run B" value={b.id} onChange={(v) => setPick({ ...pick, b: v })} />
      </div>
      {a.playbook_version_id !== b.playbook_version_id && <p className="text-sm text-warn">These runs used different playbook versions, so the numbers aren&apos;t strictly comparable.</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {METRICS.map((m) => {
          const va = m.get(a), vb = m.get(b), max = Math.max(va, vb, 1e-9);
          const bar = (v: number, other: number, name: string) => (
            <div className="flex items-center gap-2 text-sm">
              <span className="w-16 text-xs text-muted">{name}</span>
              <div className="h-2 flex-1 rounded-full bg-white/10"><div className={cn("h-full rounded-full", v < other ? "bg-ok" : v > other ? "bg-bad/70" : "bg-slate-500")} style={{ width: `${(v / max) * 100}%` }} /></div>
              <span className="w-16 text-right tabular-nums">{m.fmt(v)}</span>
            </div>
          );
          return (
            <Card key={m.label} className="space-y-2 p-4">
              <div className="text-xs uppercase tracking-wide text-muted">{m.label}</div>
              {bar(va, vb, a.mode)}{bar(vb, va, b.mode)}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
