"use client";
import { Link2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge, Card, Empty, ErrorState, Loading, Metric, type Tone } from "@/components/ui";
import { useTraceability } from "@/lib/api/live";

const TONE: Record<string, [Tone, string]> = {
  covered_passing: ["ok", "Tested, passing"], covered_failing: ["bad", "Tested, failing"],
  not_run: ["warn", "Not run yet"], uncovered: ["neutral", "Not tested"],
};

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Traceability() {
  const { slug } = useParams<{ slug: string }>();
  const { data, error, isPending, refetch } = useTraceability(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  const reqs = (data.requirements ?? []) as any[];
  if (!reqs.length) return <Empty icon={<Link2 className="size-8" />} title="No requirements yet" hint="Requirements say what your product must do. Add them in a test plan (Requirements tab of the editor) and link journeys and checks to them, and this page shows which are tested and passing." />;
  const count = (s: string) => reqs.filter((r) => r.status === s).length;
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">Which of your requirements are being tested, and are they passing? Each dot is a journey or check that proves the requirement; green passed, red failed, grey has not run.</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Requirements" info="Things the product must do, taken from your product document." value={reqs.length} />
        <Metric label="Passing" value={count("covered_passing")} tone="ok" />
        <Metric label="Failing" value={count("covered_failing")} tone={count("covered_failing") ? "bad" : undefined} />
        <Metric label="Not tested" info="Requirements that no journey or check exercises yet." value={count("uncovered")} tone={count("uncovered") ? "bad" : undefined} />
      </div>
      <p className="text-xs text-muted-foreground">Test plan version {data.version_id.slice(0, 8)}{data.latest_run_id && <> · results from run <Link className="text-brand hover:underline" href={`/apps/${slug}/runs/${data.latest_run_id}`}>{data.latest_run_id.slice(0, 8)}</Link></>}</p>
      <div className="space-y-3">
        {reqs.map((r) => {
          const [tone, label] = TONE[r.status] ?? ["neutral", r.status];
          return (
            <Card key={r.key} className="space-y-3 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="accent">{r.key}</Badge><span className="font-medium">{r.title}</span>
                {r.priority && <Badge>{r.priority}</Badge>}<Badge tone={tone} className="ml-auto">{label}</Badge>
              </div>
              {r.acceptance && <div className="text-sm text-muted-foreground">{r.acceptance}{r.prd_ref && <span className="ml-2 text-xs">({r.prd_ref})</span>}</div>}
              <div className="flex flex-wrap gap-2">
                {r.items.map((i: any) => (
                  <span key={i.key} title={`${i.relation}: ${i.title}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 font-mono text-xs">
                    <span className={`size-2 rounded-full ${i.latest_result == null ? "bg-muted-foreground" : i.latest_result.passed ? "bg-ok" : "bg-bad"}`} />{i.key}
                  </span>
                ))}
                {!r.items.length && <span className="text-xs text-muted-foreground">No journey or check tests this requirement yet.</span>}
              </div>
              {r.issue_ids.length > 0 && (
                <div className="flex flex-wrap gap-2 text-xs">{r.issue_ids.map((id: string) => <Link key={id} className="text-brand hover:underline" href={`/apps/${slug}/issues/${id}`}>Bug {id.slice(0, 6)} →</Link>)}</div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
