"use client";
import { Link2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { NeedsApi } from "@/components/live/needs-api";
import { Badge, Card, Empty, ErrorState, Loading, Metric, type Tone } from "@/components/ui";
import { USE_MOCK } from "@/lib/api/client";
import { useTraceability } from "@/lib/api/live";

const TONE: Record<string, [Tone, string]> = {
  covered_passing: ["ok", "Covered, passing"], covered_failing: ["bad", "Covered, failing"],
  not_run: ["warn", "Not run yet"], uncovered: ["neutral", "Not covered"],
};

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Traceability() {
  const { slug } = useParams<{ slug: string }>();
  const { data, error, isPending, refetch } = useTraceability(slug);
  if (USE_MOCK) return <NeedsApi what="The requirements matrix" />;
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  const reqs = (data.requirements ?? []) as any[];
  if (!reqs.length) return <Empty icon={<Link2 className="size-8" />} title="No requirements yet" hint="Add a ## Requirements section to a playbook and link flows, formulas and edge cases to it with covers: or verifies:." />;
  const count = (s: string) => reqs.filter((r) => r.status === s).length;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Requirements" value={reqs.length} />
        <Metric label="Passing" value={count("covered_passing")} tone="ok" />
        <Metric label="Failing" value={count("covered_failing")} tone={count("covered_failing") ? "bad" : undefined} />
        <Metric label="Not covered" value={count("uncovered")} tone={count("uncovered") ? "bad" : undefined} />
      </div>
      <p className="text-xs text-muted">Playbook version {data.version_id.slice(0, 8)}{data.latest_run_id && <> · results from run <Link className="text-accent hover:underline" href={`/apps/${slug}/runs/${data.latest_run_id}`}>{data.latest_run_id.slice(0, 8)}</Link></>}</p>
      <div className="space-y-3">
        {reqs.map((r) => {
          const [tone, label] = TONE[r.status] ?? ["neutral", r.status];
          return (
            <Card key={r.key} className="space-y-3 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="accent">{r.key}</Badge><span className="font-medium">{r.title}</span>
                {r.priority && <Badge>{r.priority}</Badge>}<Badge tone={tone} className="ml-auto">{label}</Badge>
              </div>
              {r.acceptance && <div className="text-sm text-muted">{r.acceptance}{r.prd_ref && <span className="ml-2 text-xs">({r.prd_ref})</span>}</div>}
              <div className="flex flex-wrap gap-2">
                {r.items.map((i: any) => (
                  <span key={i.key} title={`${i.relation}: ${i.title}`} className="inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono text-xs">
                    <span className={`size-2 rounded-full ${i.latest_result == null ? "bg-slate-500" : i.latest_result.passed ? "bg-ok" : "bg-bad"}`} />{i.key}
                  </span>
                ))}
                {!r.items.length && <span className="text-xs text-muted">Nothing covers this requirement.</span>}
              </div>
              {r.issue_ids.length > 0 && (
                <div className="flex flex-wrap gap-2 text-xs">{r.issue_ids.map((id: string) => <Link key={id} className="text-accent hover:underline" href={`/apps/${slug}/issues/${id}`}>Issue {id.slice(0, 6)} →</Link>)}</div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
