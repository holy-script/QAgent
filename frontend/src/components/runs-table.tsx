"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { ConfirmDelete } from "@/components/confirm-delete";
import { Badge, Button, Empty, SimpleTable, StatusPill, TableCell, TableRow, ago, cn, fmtMs, fmtUsd } from "@/components/ui";
import { Checkbox } from "@/components/ui/checkbox";
import { api } from "@/lib/api/client";
import type { Run } from "@/lib/api/types";
import { MODE_INFO } from "@/lib/terms";

const isLive = (r: Run) => r.status === "running" || r.status === "queued";

/** The runs list. Rows can be ticked and deleted (with their screenshots, proof and reports); runs in progress cannot. */
export function RunsTable({ slug, runs }: { slug: string; runs: Run[] }) {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [confirm, setConfirm] = useState<string[] | null>(null);
  const del = useMutation({
    mutationFn: async (ids: string[]) => { for (const id of ids) await api.deleteRun(id); return ids.length; },
    onSuccess: (n) => {
      setConfirm(null); setPicked(new Set());
      for (const k of ["runs", "dashboard", "issues", "tape"]) qc.invalidateQueries({ queryKey: [k] });
      toast.success(n === 1 ? "Run deleted" : `${n} runs deleted`);
    },
  });
  if (!runs.length) return <Empty title="No test runs yet" hint="Open the Overview tab and choose “Run now” to run your first test." />;
  const deletable = runs.filter((r) => !isLive(r)).map((r) => r.id);
  const chosen = [...picked].filter((id) => deletable.includes(id));
  const all = deletable.length > 0 && chosen.length === deletable.length;
  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const count = confirm?.length ?? 0;
  return (
    <div className="space-y-2">
      {chosen.length > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-brand/25 bg-secondary px-3 py-2 text-sm" role="status">
          <span>{chosen.length} selected</span>
          <Button variant="danger" onClick={() => setConfirm(chosen)}><Trash2 className="size-4" />Delete selected</Button>
          <button className="ml-auto text-xs text-muted-foreground underline" onClick={() => setPicked(new Set())}>Clear</button>
        </div>
      )}
      <SimpleTable head={["", "Run", "Test plan", "Mode", "Result", "Problems", "Steps", "AI speed", "AI cost", "Started", ""]}>
        {runs.map((r) => (
          <TableRow key={r.id} className={cn("hover:bg-secondary/60", picked.has(r.id) && "bg-secondary/70")}>
            <TableCell className="w-10 px-4 py-2.5">
              <Checkbox checked={picked.has(r.id)} disabled={isLive(r)} onCheckedChange={() => toggle(r.id)} aria-label={`Select run ${r.id.slice(0, 8)}`} />
            </TableCell>
            <TableCell className="px-4 py-2.5"><Link className="font-mono text-brand hover:underline" href={`/apps/${slug}/runs/${r.id}`}>{r.id.slice(0, 8)}</Link></TableCell>
            <TableCell className="px-4 py-2.5">{r.playbook_name}</TableCell>
            <TableCell className="px-4 py-2.5"><Badge tone={r.mode === "hybrid" ? "violet" : "neutral"}>{MODE_INFO[r.mode].label}</Badge></TableCell>
            <TableCell className="px-4 py-2.5"><StatusPill status={r.status} /></TableCell>
            <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.findings}</TableCell>
            <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.steps}</TableCell>
            <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.p50_decide_ms ? fmtMs(r.totals.p50_decide_ms) : "–"}</TableCell>
            <TableCell className="px-4 py-2.5 tabular-nums">{r.totals.cost_usd ? fmtUsd(r.totals.cost_usd) : "–"}</TableCell>
            <TableCell className="px-4 py-2.5 text-muted-foreground">{ago(r.started_at)}</TableCell>
            <TableCell className="px-4 py-2.5 text-right">
              {!isLive(r) && <button onClick={() => setConfirm([r.id])} aria-label={`Delete run ${r.id.slice(0, 8)}`} title="Delete this run" className="rounded-md p-1.5 text-muted-foreground hover:bg-bad-soft hover:text-bad"><Trash2 className="size-4" /></button>}
            </TableCell>
          </TableRow>
        ))}
      </SimpleTable>
      {deletable.length > 1 && (
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Checkbox checked={all} onCheckedChange={() => setPicked(all ? new Set() : new Set(deletable))} aria-label="Select all runs" />Select all finished runs
        </label>
      )}
      <ConfirmDelete open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)} title={count === 1 ? "Delete this run?" : `Delete ${count} runs?`}
        actionLabel={count === 1 ? "Delete run" : `Delete ${count} runs`} pending={del.isPending} error={del.error?.message} onConfirm={() => del.mutate(confirm ?? [])}>
        <p>{count === 1 ? "The run" : "These runs"} and {count === 1 ? "its" : "their"} screenshots, proof and reports are removed. Bugs that only {count === 1 ? "this run" : "these runs"} found disappear too.</p>
      </ConfirmDelete>
    </div>
  );
}
