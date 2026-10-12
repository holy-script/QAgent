"use client";
import { ArrowRight, Bug, Coins, Flame, Layers, Lightbulb, PlayCircle, ShieldCheck, Target } from "lucide-react";
import Link from "next/link";
import { useState, type ComponentType, type ReactNode } from "react";
import { AreaTrend, Gauge, HBars, RunsChart, SplitBar, Sparkline, StatusStrip } from "@/components/dashboard/charts";
import { Card, Empty, ErrorState, Loading, Metric, SeverityBadge, StatusPill, ago, cn, fmtUsd } from "@/components/ui";
import { useDashboard, type Dashboard as Data } from "@/lib/api/live";

const PERIODS = [7, 30, 90] as const;
const SEVERITIES = ["critical", "high", "medium", "low"];

function Panel({ icon: Icon, title, hint, right, children, className }: { icon: ComponentType<{ className?: string }>; title: string; hint?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("min-w-0 overflow-hidden", className)}>
      <div className="flex items-center gap-3 border-b bg-gradient-to-r from-secondary to-card px-5 py-3">
        <span className="grid size-8 place-items-center rounded-lg bg-chip text-brand"><Icon className="size-4" /></span>
        <div className="min-w-0 flex-1"><h3 className="text-sm font-semibold">{title}</h3>{hint && <p className="truncate text-xs text-muted-foreground">{hint}</p>}</div>
        {right}
      </div>
      <div className="p-5">{children}</div>
    </Card>
  );
}

/** One concrete suggestion from the numbers, so the dashboard ends in an action and not just charts. */
function nextStep(d: Data): { title: string; text: string; href?: string; cta?: string } {
  const worst = d.top_bugs[0];
  if (worst && (worst.severity === "critical" || worst.severity === "high")) {
    return { title: `Fix the ${worst.severity} bug first`, text: `“${worst.title}” in ${worst.app_name} is the most serious open bug. After the fix, press Repeat exactly on the failing run to check it.`, href: `/apps/${worst.app_slug}/issues/${worst.id}`, cta: "Open the bug" };
  }
  if (d.bugs_by_status.regressed) return { title: "A bug came back", text: "Something that was fixed fails again. Compare the last clean run with the latest one to see what changed.", cta: undefined };
  if (d.open_bugs) return { title: "Work through the open bugs", text: `${d.open_bugs} bugs are open. Start with the ones that break a requirement.`, href: d.top_bugs[0] ? `/apps/${d.top_bugs[0].app_slug}/issues` : undefined, cta: "See bugs" };
  if (!d.runs) return { title: "Run your first test", text: "Open an app and press Run now. A run takes about a minute." };
  return { title: "All clear", text: "No open bugs. Add more journeys to the test plans to widen what is covered." };
}

/** The home dashboard: how testing is going across every app, at a glance. */
export function Dashboard() {
  const [days, setDays] = useState<number>(30);
  const { data: d, error, isPending, refetch } = useDashboard(days);
  if (isPending) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  if (!d.apps) return null;
  const rate = d.pass_rate == null ? null : Math.round(d.pass_rate * 100);
  const tail = (f: (x: Data["series"][number]) => number) => d.series.slice(-14).map(f);
  const next = nextStep(d);
  return (
    <section aria-label="Dashboard" className="space-y-5" data-tour="dashboard">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Dashboard</h2>
        <div className="flex overflow-hidden rounded-lg border border-brand/25 bg-card shadow-xs" role="group" aria-label="Period">
          {PERIODS.map((p) => (
            <button key={p} onClick={() => setDays(p)} aria-pressed={days === p} className={cn("px-3.5 py-1.5 text-xs font-medium transition-colors", days === p ? "bg-brand text-white" : "text-secondary-foreground hover:bg-secondary")}>{p} days</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric icon={PlayCircle} label="Test runs" value={d.runs} hint={d.running ? `${d.running} running now` : `last ${d.days} days`} info="Runs started in the chosen period, across all apps." extra={<Sparkline className="mt-2" values={tail((x) => x.passed + x.failed)} />} />
        <Metric icon={ShieldCheck} label="Runs without problems" value={rate == null ? "–" : `${rate}%`} tone={rate == null ? undefined : rate >= 80 ? "ok" : "bad"} hint={`${d.passed} clean · ${d.failed} with problems`} info="Share of finished runs in which every check passed." extra={<Sparkline className="mt-2" color={rate != null && rate >= 80 ? "var(--ok)" : "var(--bad)"} values={tail((x) => (x.passed + x.failed ? x.passed / (x.passed + x.failed) : 0))} />} />
        <Metric icon={Bug} label="Open bugs" value={d.open_bugs} tone={d.open_bugs ? "bad" : "ok"} hint={`${d.bugs_by_severity.critical ?? 0} critical`} info="Bugs that are still open or came back. The same problem across runs counts once." />
        <Metric icon={Coins} label="AI cost" value={fmtUsd(d.cost_usd)} tone="warn" hint={`${fmtUsd(d.avg_cost_usd)} per run`} info="Spend on AI calls in the period: choosing actions, answering checks, planning and writing reports." extra={<Sparkline className="mt-2" color="var(--warn)" values={tail((x) => x.cost_usd)} />} />
        <Metric icon={Layers} label="Apps" value={d.apps} hint="being tested" />
        <Metric icon={Flame} label="Problems found" value={d.series.reduce((n, x) => n + x.findings, 0)} tone="violet" hint="failed checks, all runs" info="Individual failed checks. Many can be the same bug seen in different runs." extra={<Sparkline className="mt-2" color="var(--violet)" values={tail((x) => x.findings)} />} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel icon={PlayCircle} title="Runs per day" hint="Green had no problems, red did" className="xl:col-span-5">
          {d.runs ? <RunsChart series={d.series} label={`Runs per day over the last ${d.days} days: ${d.passed} without problems, ${d.failed} with problems`} /> : <Empty title="No runs in this period" hint="Pick a longer period, or run a test from an app." />}
        </Panel>
        <Panel icon={Coins} title="AI cost per day" hint={`${fmtUsd(d.cost_usd)} in ${d.days} days`} className="xl:col-span-4">
          <AreaTrend series={d.series} pick={(x) => x.cost_usd ?? 0} format={fmtUsd} label={`AI cost per day over the last ${d.days} days`} />
        </Panel>
        <Panel icon={Target} title="Clean runs" hint="Share of finished runs with no problems" className="xl:col-span-3">
          <Gauge value={d.pass_rate} label="Share of runs without problems" sub={`${d.passed} of ${d.passed + d.failed} finished runs`} />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-12">
        <Panel icon={Bug} title="Open bugs by severity" className="xl:col-span-3">
          {d.open_bugs ? <HBars rows={SEVERITIES.map((s) => ({ label: s, value: d.bugs_by_severity[s] ?? 0, tone: s }))} /> : <p className="text-sm text-muted-foreground">No open bugs. Nice.</p>}
          <div className="mt-5 border-t pt-4"><SplitBar parts={[{ label: "open", value: d.bugs_by_status.open ?? 0, color: "bg-bad" }, { label: "came back", value: d.bugs_by_status.regressed ?? 0, color: "bg-warn" }, { label: "fixed", value: d.bugs_by_status.resolved ?? 0, color: "bg-ok" }]} /></div>
        </Panel>
        <Panel icon={Layers} title="App health" hint="Last 12 runs, pass rate, bugs" className="xl:col-span-5">
          <ul className="divide-y">
            {d.per_app.map((a) => (
              <li key={a.slug}>
                <Link href={`/apps/${a.slug}`} className="flex items-center gap-3 rounded-lg py-2.5 text-sm transition-colors hover:bg-secondary/60 sm:px-2 sm:-mx-2">
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-xs font-bold text-primary-foreground">{a.name.slice(0, 2).toUpperCase()}</span>
                  <span className="min-w-0 flex-1 truncate font-medium">{a.name}</span>
                  <StatusStrip statuses={a.recent_statuses} />
                  <span className="w-12 text-right tabular-nums text-muted-foreground">{a.pass_rate == null ? "–" : `${Math.round(a.pass_rate * 100)}%`}</span>
                  <span className={cn("w-16 text-right text-xs", a.open_bugs ? "font-medium text-bad" : "text-muted-foreground")}>{a.open_bugs} {a.open_bugs === 1 ? "bug" : "bugs"}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel icon={PlayCircle} title="Latest runs" className="lg:col-span-2 xl:col-span-4">
          {!d.recent_runs.length ? <p className="text-sm text-muted-foreground">Nothing has run yet.</p> : (
            <ul className="divide-y">
              {d.recent_runs.slice(0, 6).map((r) => (
                <li key={r.id}>
                  <Link href={`/apps/${r.app_slug}/runs/${r.id}`} className="flex items-center gap-3 rounded-lg py-2 text-sm transition-colors hover:bg-secondary/60 sm:px-2 sm:-mx-2">
                    <StatusPill status={r.status} />
                    <span className="min-w-0 flex-1 truncate">{r.app_name}</span>
                    <span className="text-xs text-muted-foreground">{r.findings ? `${r.findings} problems` : "clean"}</span>
                    <span className="w-14 text-right text-xs text-muted-foreground">{r.started_at ? ago(r.started_at) : ""}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel icon={Bug} title="Worst open bugs" hint="Most serious first" className="xl:col-span-8">
          {!d.top_bugs.length ? <p className="text-sm text-muted-foreground">No open bugs.</p> : (
            <ul className="grid gap-2 md:grid-cols-2">
              {d.top_bugs.map((b) => (
                <li key={b.id}>
                  <Link href={`/apps/${b.app_slug}/issues/${b.id}`} className="card-lift flex h-full items-center gap-3 rounded-lg border bg-gradient-to-br from-card to-secondary/50 p-3 text-sm">
                    <SeverityBadge severity={b.severity} />
                    <span className="min-w-0 flex-1"><span className="line-clamp-2 font-medium">{b.title}</span><span className="text-xs text-muted-foreground">{b.app_name} · seen in {b.occurrences} {b.occurrences === 1 ? "run" : "runs"}</span></span>
                    <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Card className="relative min-w-0 overflow-hidden bg-hero p-5 text-white xl:col-span-4">
          <span className="grid size-9 place-items-center rounded-lg bg-white/15"><Lightbulb className="size-[18px] text-[#f3d58a]" /></span>
          <h3 className="mt-3 text-base font-semibold">{next.title}</h3>
          <p className="mt-1 text-sm text-white/90">{next.text}</p>
          {next.href && next.cta && <Link href={next.href} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">{next.cta}<ArrowRight className="size-4" /></Link>}
        </Card>
      </div>
    </section>
  );
}
