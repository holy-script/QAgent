"use client";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { HBars, RunBars, StatusStrip } from "@/components/dashboard/charts";
import { Card, Empty, ErrorState, Loading, Metric, SeverityBadge, StatusPill, ago, cn, fmtUsd } from "@/components/ui";
import { useDashboard } from "@/lib/api/live";

const PERIODS = [7, 30, 90] as const;
const SEVERITIES = ["critical", "high", "medium", "low"];

/** The home dashboard: how testing is going across every app, at a glance. */
export function Dashboard() {
  const [days, setDays] = useState<number>(30);
  const { data: d, error, isPending, refetch } = useDashboard(days);
  if (isPending) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  if (!d.apps) return null;
  const rate = d.pass_rate == null ? null : Math.round(d.pass_rate * 100);
  return (
    <section aria-label="Dashboard" className="space-y-4" data-tour="dashboard">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-medium">Dashboard</h2>
        <div className="flex overflow-hidden rounded-lg border border-border" role="group" aria-label="Period">
          {PERIODS.map((p) => (
            <button key={p} onClick={() => setDays(p)} aria-pressed={days === p} className={cn("px-3 py-1.5 text-xs", days === p ? "bg-brand/20 text-brand" : "text-muted-foreground hover:bg-foreground/5")}>{p} days</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric label="Test runs" value={d.runs} hint={d.running ? `${d.running} running now` : `last ${d.days} days`} info="Runs started in the chosen period, across all apps." />
        <Metric label="Runs without problems" value={rate == null ? "–" : `${rate}%`} tone={rate == null ? undefined : rate >= 80 ? "ok" : "bad"} hint={`${d.passed} clean · ${d.failed} with problems`} info="Share of finished runs in which every check passed." />
        <Metric label="Open bugs" value={d.open_bugs} tone={d.open_bugs ? "bad" : "ok"} hint={`${d.bugs_by_severity.critical ?? 0} critical`} info="Bugs that are still open or came back. The same problem across runs counts once." />
        <Metric label="AI cost" value={fmtUsd(d.cost_usd)} hint={`${fmtUsd(d.avg_cost_usd)} per run`} info="Spend on AI calls in the period: choosing actions, answering checks, planning and writing reports." />
        <Metric label="Apps" value={d.apps} hint="being tested" />
        <Metric label="Problems found" value={d.series.reduce((n, x) => n + x.findings, 0)} hint="failed checks, all runs" info="Individual failed checks. Many of them can be the same bug seen in different runs." />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="min-w-0 space-y-2 p-5 xl:col-span-2">
          <h3 className="text-sm font-medium">Runs per day</h3>
          {d.runs ? <RunBars series={d.series} label={`Runs per day over the last ${d.days} days: ${d.passed} without problems, ${d.failed} with problems`} /> : <Empty title="No runs in this period" hint="Pick a longer period, or run a test from an app." />}
        </Card>
        <Card className="min-w-0 space-y-4 p-5">
          <h3 className="text-sm font-medium">Open bugs by severity</h3>
          {d.open_bugs ? <HBars rows={SEVERITIES.map((s) => ({ label: s, value: d.bugs_by_severity[s] ?? 0, tone: s }))} /> : <p className="text-sm text-muted-foreground">No open bugs. Nice.</p>}
          <div className="flex flex-wrap gap-x-4 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
            <span>{d.bugs_by_status.open ?? 0} open</span><span>{d.bugs_by_status.regressed ?? 0} came back</span><span>{d.bugs_by_status.resolved ?? 0} fixed</span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <Card className="min-w-0 p-5">
          <h3 className="mb-3 text-sm font-medium">App health</h3>
          <ul className="divide-y">
            {d.per_app.map((a) => (
              <li key={a.slug}>
                <Link href={`/apps/${a.slug}`} className="flex items-center gap-3 py-2.5 text-sm hover:text-brand">
                  <span className="min-w-0 flex-1 truncate font-medium">{a.name}</span>
                  <StatusStrip statuses={a.recent_statuses} />
                  <span className="w-12 text-right tabular-nums text-muted-foreground">{a.pass_rate == null ? "–" : `${Math.round(a.pass_rate * 100)}%`}</span>
                  <span className={cn("w-16 text-right text-xs", a.open_bugs ? "text-bad" : "text-muted-foreground")}>{a.open_bugs} {a.open_bugs === 1 ? "bug" : "bugs"}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="min-w-0 p-5">
          <h3 className="mb-3 text-sm font-medium">Latest runs</h3>
          {!d.recent_runs.length ? <p className="text-sm text-muted-foreground">Nothing has run yet.</p> : (
            <ul className="divide-y">
              {d.recent_runs.slice(0, 6).map((r) => (
                <li key={r.id}>
                  <Link href={`/apps/${r.app_slug}/runs/${r.id}`} className="flex items-center gap-3 py-2 text-sm hover:text-brand">
                    <StatusPill status={r.status} />
                    <span className="min-w-0 flex-1 truncate">{r.app_name}</span>
                    <span className="text-xs text-muted-foreground">{r.findings ? `${r.findings} problems` : "clean"}</span>
                    <span className="w-16 text-right text-xs text-muted-foreground">{r.started_at ? ago(r.started_at) : ""}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="min-w-0 p-5 lg:col-span-2 xl:col-span-1">
          <h3 className="mb-3 text-sm font-medium">Worst open bugs</h3>
          {!d.top_bugs.length ? <p className="text-sm text-muted-foreground">No open bugs.</p> : (
            <ul className="divide-y">
              {d.top_bugs.map((b) => (
                <li key={b.id}>
                  <Link href={`/apps/${b.app_slug}/issues/${b.id}`} className="flex items-center gap-3 py-2 text-sm hover:text-brand">
                    <SeverityBadge severity={b.severity} />
                    <span className="min-w-0 flex-1 truncate">{b.title}</span>
                    <ArrowRight className="size-3.5 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </section>
  );
}
