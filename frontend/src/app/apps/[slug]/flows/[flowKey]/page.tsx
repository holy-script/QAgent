"use client";
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
        <Link href={`/apps/${slug}/flows`} aria-label="Back to flows" className="text-muted hover:text-foreground"><ChevronLeft className="size-5" /></Link>
        <h2 className="text-lg font-medium">{key}</h2>
      </div>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-muted"><tr>{["Run", "Mode", "Result", "Findings", "Duration", "When"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-line">
            {flow.runs.map((r) => (
              <tr key={r.run_id} className="hover:bg-white/[0.03]">
                <td className="px-4 py-2.5"><Link className="font-mono text-accent hover:underline" href={`/apps/${slug}/runs/${r.run_id}`}>{r.run_id.slice(0, 10)}</Link></td>
                <td className="px-4 py-2.5"><Badge tone={r.mode === "hybrid" ? "violet" : "neutral"}>{r.mode}</Badge></td>
                <td className="px-4 py-2.5"><StatusPill status={r.status} /></td>
                <td className="px-4 py-2.5 tabular-nums">{r.findings}</td>
                <td className="px-4 py-2.5 tabular-nums">{fmtMs(r.duration_ms)}</td>
                <td className="px-4 py-2.5 text-muted">{ago(r.started_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
