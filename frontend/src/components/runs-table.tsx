"use client";
import Link from "next/link";
import { Empty, StatusPill, Badge, ago, fmtMs, fmtUsd } from "@/components/ui";
import type { Run } from "@/lib/api/types";

export function RunsTable({ slug, runs }: { slug: string; runs: Run[] }) {
  if (!runs.length) return <Empty title="No runs yet" hint="Start a run from the Overview tab." />;
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-left text-sm">
        <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-muted">
          <tr>{["Run", "Playbook", "Mode", "Status", "Findings", "Steps", "p50 decide", "Cost", "Started"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">
          {runs.map((r) => (
            <tr key={r.id} className="hover:bg-white/[0.03]">
              <td className="px-4 py-2.5"><Link className="font-mono text-accent hover:underline" href={`/apps/${slug}/runs/${r.id}`}>{r.id.slice(0, 10)}</Link></td>
              <td className="px-4 py-2.5">{r.playbook_name}</td>
              <td className="px-4 py-2.5"><Badge tone={r.mode === "hybrid" ? "violet" : "neutral"}>{r.mode}</Badge></td>
              <td className="px-4 py-2.5"><StatusPill status={r.status} /></td>
              <td className="px-4 py-2.5 tabular-nums">{r.totals.findings}</td>
              <td className="px-4 py-2.5 tabular-nums">{r.totals.steps}</td>
              <td className="px-4 py-2.5 tabular-nums">{r.totals.p50_decide_ms ? fmtMs(r.totals.p50_decide_ms) : "–"}</td>
              <td className="px-4 py-2.5 tabular-nums">{r.totals.cost_usd ? fmtUsd(r.totals.cost_usd) : "–"}</td>
              <td className="px-4 py-2.5 text-muted">{ago(r.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
