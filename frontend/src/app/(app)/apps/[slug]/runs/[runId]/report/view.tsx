"use client";
import { ChevronLeft, Download, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge, Button, Card, ErrorState, Loading, Metric, SeverityBadge, StatusPill, fmtMs, fmtUsd, type Tone } from "@/components/ui";
import { API_URL } from "@/lib/api/client";
import { useRegenerateReport, useRunReport } from "@/lib/api/live";

/* eslint-disable @typescript-eslint/no-explicit-any */
const REQ_TONE: Record<string, Tone> = { covered_passing: "ok", covered_failing: "bad", not_run: "warn", not_covered: "neutral" };

export default function RunReport() {
  const { slug, runId } = useParams<{ slug: string; runId: string }>();
  const { data: report, error, isPending } = useRunReport(runId);
  const regen = useRegenerateReport(runId);
  if (isPending && !error) return <Loading label="Loading report…" />;
  if (error || !report) {
    return (
      <div className="space-y-3">
        <ErrorState error={error ?? new Error("No report yet")} />
        <div className="text-center"><Button onClick={() => regen.mutate()} disabled={regen.isPending}><RefreshCw className="size-4" />{regen.isPending ? "Generating…" : "Generate report"}</Button></div>
      </div>
    );
  }
  const c = report.content as Record<string, any>;
  const exportUrl = (f: string) => `${API_URL}/reports/${report.id}/export?format=${f}`;
  const cats = Object.entries((c.findings_by_category ?? {}) as Record<string, any[]>);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href={`/apps/${slug}/runs/${runId}`} className="text-muted-foreground hover:text-foreground" aria-label="Back to the run"><ChevronLeft className="size-5" /></Link>
        <div><h2 className="text-lg font-medium">Test report</h2><p className="text-sm text-muted-foreground">A summary of one test run: what passed, what broke, and what to do next. Everything here comes from recorded evidence.</p></div>
        <StatusPill status={c.run?.status} /><Badge>{c.run?.mode}</Badge>
        <span className="font-mono text-xs text-muted-foreground">{runId}</span>
        <div className="ml-auto flex gap-2">
          {(["md", "html", "pdf"] as const).map((f) => (
            <a key={f} href={exportUrl(f)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/[0.03] px-3 py-2 text-sm hover:bg-secondary"><Download className="size-4" />{f.toUpperCase()}</a>
          ))}
          <Button onClick={() => regen.mutate()} disabled={regen.isPending} aria-label="Rebuild the report"><RefreshCw className="size-4" />{regen.isPending ? "…" : "Rebuild"}</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Problems found" value={c.summary?.total_findings} tone={c.summary?.total_findings ? "bad" : "ok"} />
        <Metric label="New bugs" info="Problems never seen in earlier runs." value={c.summary?.issues?.new ?? 0} tone={c.summary?.issues?.new ? "bad" : undefined} />
        <Metric label="Still open" info="Bugs seen before that this run found again." value={c.summary?.issues?.recurring ?? 0} />
        <Metric label="Fixed" info="Bugs from earlier runs that this run no longer found." value={c.summary?.issues?.resolved ?? 0} tone={c.summary?.issues?.resolved ? "ok" : undefined} />
        <Metric label="AI cost" value={fmtUsd(c.summary?.cost_usd ?? 0)} hint={fmtMs(c.summary?.duration_ms ?? 0)} />
      </div>

      <Section title="Journeys">
        <Card className="divide-y divide-border text-sm">
          {(c.summary?.flows ?? []).map((f: any) => (
            <div key={f.flow_key} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <span className="font-mono text-xs">{f.flow_key}</span><StatusPill status={f.status === "passed_with_findings" ? "failed" : f.status} />
              <span className="text-xs text-muted-foreground">{f.step_count} steps · {fmtMs(f.duration_ms)}</span>
              {f.findings > 0 && <Badge tone="bad">{f.findings} problem{f.findings === 1 ? "" : "s"}</Badge>}
              {f.failure_reason && <span className="truncate text-xs text-bad">{f.failure_reason}</span>}
            </div>
          ))}
        </Card>
      </Section>

      <Section title="Requirements" action={<Link className="text-xs text-brand hover:underline" href={`/apps/${slug}/traceability`}>See all requirements →</Link>}>
        <Card className="divide-y divide-border text-sm">
          {(c.requirements ?? []).map((r: any) => (
            <div key={r.key} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
              <Badge tone="accent">{r.key}</Badge><span>{r.title}</span><Badge tone={REQ_TONE[r.status]} className="ml-auto">{String(r.status).replace("_", " ")}</Badge>
            </div>
          ))}
        </Card>
      </Section>

      <Section title="Problems by type">
        {cats.length === 0 && <div className="text-sm text-muted-foreground">No findings.</div>}
        {cats.map(([cat, items]) => (
          <div key={cat} className="space-y-1.5">
            <div className="text-xs font-medium capitalize text-muted-foreground">{cat} ({items.length})</div>
            {items.map((f) => (
              <Card key={f.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm">
                <SeverityBadge severity={f.severity} /><span>{f.title}</span>
                {f.judged_by !== "code" && <Badge tone="warn">judged by AI</Badge>}
                <span className="ml-auto flex gap-3 text-xs">
                  <span className="text-muted-foreground">{f.flow} · step {f.step_seq}</span>
                  {f.issue_id && <Link className="text-brand hover:underline" href={`/apps/${slug}/issues/${f.issue_id}`}>Bug →</Link>}
                </span>
              </Card>
            ))}
          </div>
        ))}
      </Section>

      <Section title="Speed">
        <Card className="divide-y divide-border font-mono text-xs">
          {(c.performance?.slowest_api_calls ?? []).map((n: any) => <div key={n.id} className="flex gap-3 px-4 py-2"><Badge tone={n.status >= 400 ? "bad" : "ok"}>{n.status}</Badge><span>{n.method}</span><span className="truncate">{n.url}</span><span className="ml-auto text-muted-foreground">{fmtMs(n.duration_ms)}</span></div>)}
          {(c.performance?.longest_waits ?? []).map((w: any) => <div key={w.step_id} className="flex gap-3 px-4 py-2"><span>wait</span><span>{w.flow} · step {w.step_seq}</span><span className="ml-auto text-muted-foreground">{fmtMs(w.settle_ms)}</span></div>)}
        </Card>
      </Section>

      <Section title="Suggested next steps">
        {(c.recommendations ?? []).length === 0 && <div className="text-sm text-muted-foreground">Suggested next steps: {c.recommendations_status}.</div>}
        {(c.recommendations ?? []).map((r: any, i: number) => (
          <Card key={i} className="space-y-1 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2"><Badge tone="violet">{r.category}</Badge><Badge>{r.confidence} confidence</Badge><Badge>effort {r.effort}</Badge></div>
            <div className="font-medium">{r.text}</div><div className="text-muted-foreground">{r.rationale}</div>
            <div className="flex flex-wrap gap-1 pt-1">{(r.evidence_finding_ids ?? []).map((id: string) => <Link key={id} href={`/apps/${slug}/runs/${runId}?tab=findings`} className="font-mono text-[11px] text-brand hover:underline">{id}</Link>)}</div>
          </Card>
        ))}
        {(c.recommendations_dropped ?? []).length > 0 && <div className="text-xs text-muted-foreground">{c.recommendations_dropped.length} suggestion(s) that could not be backed by evidence were left out.</div>}
      </Section>

      <Section title="How reliable was this run?">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>{c.test_quality?.escalations} step(s) double-checked by the stronger AI</li>
          <li>{(c.test_quality?.low_confidence_decisions ?? []).length} choice(s) the AI was not very sure about (a hint to add notes to the test plan)</li>
          <li>{c.test_quality?.judged_findings} problem(s) were judged by AI rather than by a fixed rule; {c.test_quality?.checks_run} checks were run</li>
        </ul>
      </Section>
      <div className="font-mono text-[11px] text-muted-foreground">playbook hash {c.integrity?.playbook_hash} · manifest hash {c.integrity?.manifest_hash}</div>
    </div>
  );
}

const Section = ({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) => (
  <section className="space-y-2"><div className="flex items-center"><h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3><span className="ml-auto">{action}</span></div>{children}</section>
);
