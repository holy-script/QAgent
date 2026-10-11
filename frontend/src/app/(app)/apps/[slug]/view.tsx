"use client";
import { useParams } from "next/navigation";
import { RunLauncher } from "@/components/run-launcher";
import { RunsTable } from "@/components/runs-table";
import { Card, ErrorState, Loading, Metric, fmtMs } from "@/components/ui";
import { useApp, useRuns } from "@/lib/api/hooks";
import { GettingStarted } from "@/components/getting-started";
import { OverviewLive } from "@/components/live/overview-live";

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
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-6">
        <GettingStarted slug={slug} />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="Test runs" value={runs.length} info="Each run walks every journey in a test plan in a real browser." />
          <Metric label="Runs without problems" info="Share of finished runs in which every check passed." value={passRate == null ? "–" : `${passRate}%`} tone={passRate == null ? undefined : passRate >= 80 ? "ok" : "bad"} />
          <Metric label="Problems in the last run" info="Checks that failed in the most recent run. The same problem across runs is tracked as one bug." value={last?.totals.findings ?? "–"} tone={last?.totals.findings ? "bad" : undefined} />
          <Metric label="AI speed" info="Typical time the AI takes to choose the next action." value={last?.totals.p50_decide_ms ? fmtMs(last.totals.p50_decide_ms) : "–"} hint="last run" />
        </div>
        <section className="space-y-3">
          <h2 className="font-medium">Recent test runs</h2>
          <RunsTable slug={slug} runs={runs.slice(0, 5)} />
        </section>
        <OverviewLive slug={slug} />
        {app?.description && <Card className="p-5 text-sm text-muted-foreground">{app.description}</Card>}
      </div>
      <RunLauncher slug={slug} />
    </div>
  );
}
