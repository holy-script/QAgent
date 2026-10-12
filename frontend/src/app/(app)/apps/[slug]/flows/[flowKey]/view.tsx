"use client";
import { SimpleTable, TableCell, TableRow } from "@/components/ui";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge, Empty, ErrorState, Loading, StatusPill, ago, fmtMs } from "@/components/ui";
import { useFlowHistory } from "@/lib/api/hooks";

export default function FlowHistoryPage() {
  const { slug, flowKey } = useParams<{ slug: string; flowKey: string }>();
  const key = decodeURIComponent(flowKey);
  const { data, error, isPending, refetch } = useFlowHistory(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  const flow = data.find((f) => f.flow_key === key);
  if (!flow) return <Empty title={`No history for “${key}”`} />;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Link href={`/apps/${slug}/flows`} aria-label="Back to flows" className="text-muted-foreground hover:text-foreground"><ChevronLeft className="size-5" /></Link>
        <h2 className="text-lg font-medium">{key}</h2>
      </div>
      <SimpleTable head={["Run", "Mode", "Result", "Findings", "Duration", "When"]}>
            {flow.runs.map((r) => (
              <TableRow key={r.run_id} className="hover:bg-secondary/60">
                <TableCell className="px-4 py-2.5"><Link className="font-mono text-brand hover:underline" href={`/apps/${slug}/runs/${r.run_id}`}>{r.run_id.slice(0, 10)}</Link></TableCell>
                <TableCell className="px-4 py-2.5"><Badge tone={r.mode === "hybrid" ? "violet" : "neutral"}>{r.mode}</Badge></TableCell>
                <TableCell className="px-4 py-2.5"><StatusPill status={r.status} /></TableCell>
                <TableCell className="px-4 py-2.5 tabular-nums">{r.findings}</TableCell>
                <TableCell className="px-4 py-2.5 tabular-nums">{fmtMs(r.duration_ms)}</TableCell>
                <TableCell className="px-4 py-2.5 text-muted-foreground">{ago(r.started_at)}</TableCell>
              </TableRow>
            ))}
      </SimpleTable>
    </div>
  );
}
