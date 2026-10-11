"use client";
import { useParams } from "next/navigation";
import { RunLauncher } from "@/components/run-launcher";
import { RunsTable } from "@/components/runs-table";
import { Card, ErrorState, Loading, Metric, fmtMs } from "@/components/ui";
import { useApp, useRuns } from "@/lib/api/hooks";
import { OverviewLive } from "@/components/live/overview-live";
import { USE_MOCK } from "@/lib/api/client";

export default function Overview() {
  const { slug } = useParams<{ slug: string }>();
  const { data: app } = useApp(slug);
  const { data: runs, error, isPending, refetch } = useRuns(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;

  const done = runs.filter((r) => r.status !== "running");
  const passRate = done.length ? Math.round((done.filter((r) => r.status === "passed").length / done.length) * 100) : null;
  const last = done[0];
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="Runs" value={runs.length} />
          <Metric label="Pass rate" value={passRate == null ? "–" : `${passRate}%`} tone={passRate == null ? undefined : passRate >= 80 ? "ok" : "bad"} />
          <Metric label="Findings (last run)" value={last?.totals.findings ?? "–"} tone={last?.totals.findings ? "bad" : undefined} />
          <Metric label="p50 decide" value={last?.totals.p50_decide_ms ? fmtMs(last.totals.p50_decide_ms) : "–"} hint="last run" />
        </div>
        <section className="space-y-3">
          <h2 className="font-medium">Recent runs</h2>
          <RunsTable slug={slug} runs={runs.slice(0, 5)} />
        </section>
        {!USE_MOCK && <OverviewLive slug={slug} />}
        {app?.description && <Card className="p-5 text-sm text-muted">{app.description}</Card>}
      </div>
      <RunLauncher slug={slug} />
    </div>
  );
}
