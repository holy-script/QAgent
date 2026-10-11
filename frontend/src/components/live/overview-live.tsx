"use client";
import Link from "next/link";
import { Badge, Card, SeverityBadge, type Tone } from "@/components/ui";
import { useIssues, useTraceability } from "@/lib/api/live";

const ORDER = ["critical", "high", "medium", "low"];
const TONE: Record<string, Tone> = { open: "bad", regressed: "warn" };

/** Overview extras that only exist on the real backend: requirement coverage and the top open issues. */
export function OverviewLive({ slug }: { slug: string }) {
  const { data: issues } = useIssues(slug);
  const { data: trace } = useTraceability(slug);
  const open = (issues ?? []).filter((i) => i.status !== "resolved").sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  const reqs = (trace?.requirements ?? []) as { status: string }[];
  const n = (s: string) => reqs.filter((r) => r.status === s).length;
  return (
    <>
      {reqs.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center"><h2 className="font-medium">Requirement coverage</h2><Link href={`/apps/${slug}/traceability`} className="ml-auto text-xs text-accent hover:underline">Open matrix →</Link></div>
          <Card className="flex flex-wrap gap-6 p-4 text-sm">
            <span><b className="text-ok">{n("covered_passing")}</b> passing</span>
            <span><b className="text-bad">{n("covered_failing")}</b> failing</span>
            <span><b className="text-warn">{n("not_run")}</b> not run</span>
            <span><b>{n("uncovered")}</b> not covered</span>
          </Card>
        </section>
      )}
      <section className="space-y-3">
        <div className="flex items-center"><h2 className="font-medium">Open issues</h2><Link href={`/apps/${slug}/issues`} className="ml-auto text-xs text-accent hover:underline">All issues →</Link></div>
        {!open.length ? <Card className="p-4 text-sm text-muted">No open issues.</Card> : (
          <Card className="divide-y divide-line">
            {open.slice(0, 5).map((i) => (
              <Link key={i.id} href={`/apps/${slug}/issues/${i.id}`} className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-white/[0.03]">
                <SeverityBadge severity={i.severity} /><span className="min-w-0 flex-1 truncate">{i.title}</span>
                <Badge tone={TONE[i.status]}>{i.status}</Badge><span className="text-xs tabular-nums text-muted">{i.occurrences}×</span>
              </Link>
            ))}
          </Card>
        )}
      </section>
    </>
  );
}
