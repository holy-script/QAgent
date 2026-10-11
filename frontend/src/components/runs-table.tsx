"use client";
import { SimpleTable, TableCell, TableRow } from "@/components/ui";
import { MODE_INFO } from "@/lib/terms";
import Link from "next/link";
import { Empty, StatusPill, Badge, ago, fmtMs, fmtUsd } from "@/components/ui";
import type { Run } from "@/lib/api/types";

export function RunsTable({ slug, runs }: { slug: string; runs: Run[] }) {
  if (!runs.length) return <Empty title="No test runs yet" hint="Open the Overview tab and choose “Run now” to run your first test." />;
  return (
    <SimpleTable head={["Run", "Test plan", "Mode", "Result", "Problems", "Steps", "AI speed", "AI cost", "Started"]}>
          {runs.map((r) => (
            <TableRow key={r.id} className="hover:bg-foreground/[0.03]">
              <TableCell className="px-4 py-2.5"><Link className="font-mono text-brand hover:underline" href={`/apps/${slug}/runs/${r.id}`}>{r.id.slice(0, 8)}</Link></TableCell>
              <TableCell className="px-4 py-2.5">{r.playbook_name}</TableCell>
              <TableCell className="px-4 py-2.5"><Badge tone={r.mode === "hybrid" ? "violet" : "neutral"}>{MODE_INFO[r.mode].label}</Badge></TableCell>
              <TableCell className="px-4 py-2.5"><StatusPill status={r.status} /></TableCell>
              <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.findings}</TableCell>
              <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.steps}</TableCell>
              <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.p50_decide_ms ? fmtMs(r.totals.p50_decide_ms) : "–"}</TableCell>
              <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.cost_usd ? fmtUsd(r.totals.cost_usd) : "–"}</TableCell>
              <TableCell className="px-4 py-2.5 text-muted-foreground">{ago(r.started_at)}</TableCell>
            </TableRow>
          ))}
      </SimpleTable>
  );
}
