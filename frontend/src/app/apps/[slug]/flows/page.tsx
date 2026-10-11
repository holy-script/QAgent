"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, Empty, ErrorState, Loading, SeverityBadge, StatusPill } from "@/components/ui";
import { useFlowHistory } from "@/lib/api/hooks";

export default function Flows() {
  const { slug } = useParams<{ slug: string }>();
  const { data, error, isPending, refetch } = useFlowHistory(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  if (!data.length) return <Empty title="No journeys have run yet" hint="A journey is one path a user takes through your app. They appear here after the first completed test run." />;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {data.map((f) => {
        const pass = f.runs.filter((r) => r.status === "passed").length;
        return (
          <Link key={f.flow_key} href={`/apps/${slug}/flows/${encodeURIComponent(f.flow_key)}`}>
            <Card className="space-y-3 p-4 transition hover:border-brand/50">
              <div className="flex items-center gap-2"><span className="font-medium">{f.flow_key}</span><SeverityBadge severity={f.severity} /><span className="ml-auto text-xs text-muted-foreground">{pass} of {f.runs.length} runs passed</span></div>
              <div className="flex gap-1" aria-label="Results of recent runs, oldest first">
                {f.runs.slice(0, 20).reverse().map((r) => <span key={r.run_id} title={`${r.run_id}: ${r.status}`} className={`h-6 w-2 rounded-sm ${r.status === "passed" ? "bg-ok" : "bg-bad"}`} />)}
              </div>
              {f.runs[0] && <div className="flex items-center gap-2 text-xs text-muted-foreground">Latest <StatusPill status={f.runs[0].status} /></div>}
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
