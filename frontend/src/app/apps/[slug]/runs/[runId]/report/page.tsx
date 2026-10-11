"use client";
import { ChevronLeft, Download, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { NeedsApi } from "@/components/live/needs-api";
import { Badge, Button, Card, ErrorState, Loading, Metric, SeverityBadge, StatusPill, fmtMs, fmtUsd, type Tone } from "@/components/ui";
import { API_URL, USE_MOCK } from "@/lib/api/client";
import { useRegenerateReport, useRunReport } from "@/lib/api/live";

/* eslint-disable @typescript-eslint/no-explicit-any */
const REQ_TONE: Record<string, Tone> = { covered_passing: "ok", covered_failing: "bad", not_run: "warn", not_covered: "neutral" };

export default function RunReport() {
  const { slug, runId } = useParams<{ slug: string; runId: string }>();
  const { data: report, error, isPending } = useRunReport(runId);
  const regen = useRegenerateReport(runId);
  if (USE_MOCK) return <NeedsApi what="Reports" />;
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
        <Link href={`/apps/${slug}/runs/${runId}`} className="text-muted hover:text-foreground" aria-label="Back to run"><ChevronLeft className="size-5" /></Link>
        <h2 className="text-lg font-medium">Run report</h2>
        <StatusPill status={c.run?.status} /><Badge>{c.run?.mode}</Badge>
        <span className="font-mono text-xs text-muted">{runId}</span>
        <div className="ml-auto flex gap-2">
          {(["md", "html", "pdf"] as const).map((f) => (
            <a key={f} href={exportUrl(f)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-line bg-white/[0.03] px-3 py-2 text-sm hover:bg-white/[0.08]"><Download className="size-4" />{f.toUpperCase()}</a>
          ))}
          <Button onClick={() => regen.mutate()} disabled={regen.isPending} aria-label="Regenerate report"><RefreshCw className="size-4" />{regen.isPending ? "…" : "Regenerate"}</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Findings" value={c.summary?.total_findings} tone={c.summary?.total_findings ? "bad" : "ok"} />
        <Metric label="New issues" value={c.summary?.issues?.new ?? 0} tone={c.summary?.issues?.new ? "bad" : undefined} />
        <Metric label="Recurring" value={c.summary?.issues?.recurring ?? 0} />
        <Metric label="Resolved" value={c.summary?.issues?.resolved ?? 0} tone={c.summary?.issues?.resolved ? "ok" : undefined} />
        <Metric label="Cost" value={fmtUsd(c.summary?.cost_usd ?? 0)} hint={fmtMs(c.summary?.duration_ms ?? 0)} />
      </div>

      <Section title="Flows">
        <Card className="divide-y divide-line text-sm">
          {(c.summary?.flows ?? []).map((f: any) => (
            <div key={f.flow_key} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <span className="font-mono text-xs">{f.flow_key}</span><StatusPill status={f.status === "passed_with_findings" ? "failed" : f.status} />
              <span className="text-xs text-muted">{f.step_count} steps · {fmtMs(f.duration_ms)}</span>
              {f.findings > 0 && <Badge tone="bad">{f.findings} findings</Badge>}
              {f.failure_reason && <span className="truncate text-xs text-bad">{f.failure_reason}</span>}
            </div>
          ))}
        </Card>
      </Section>

      <Section title="Requirements coverage" action={<Link className="text-xs text-accent hover:underline" href={`/apps/${slug}/traceability`}>Open matrix →</Link>}>
        <Card className="divide-y divide-line text-sm">
          {(c.requirements ?? []).map((r: any) => (
            <div key={r.key} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
              <Badge tone="accent">{r.key}</Badge><span>{r.title}</span><Badge tone={REQ_TONE[r.status]} className="ml-auto">{String(r.status).replace("_", " ")}</Badge>
            </div>
          ))}
        </Card>
      </Section>

      <Section title="Findings by category">
        {cats.length === 0 && <div className="text-sm text-muted">No findings.</div>}
        {cats.map(([cat, items]) => (
          <div key={cat} className="space-y-1.5">
            <div className="text-xs font-medium capitalize text-muted">{cat} ({items.length})</div>
            {items.map((f) => (
              <Card key={f.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm">
                <SeverityBadge severity={f.severity} /><span>{f.title}</span>
                {f.judged_by !== "code" && <Badge tone="warn">judged by {f.judged_by}</Badge>}
                <span className="ml-auto flex gap-3 text-xs">
                  <span className="text-muted">{f.flow} · step {f.step_seq}</span>
                  {f.issue_id && <Link className="text-accent hover:underline" href={`/apps/${slug}/issues/${f.issue_id}`}>Issue →</Link>}
                </span>
              </Card>
            ))}
          </div>
        ))}
      </Section>

      <Section title="Performance">
        <Card className="divide-y divide-line font-mono text-xs">
          {(c.performance?.slowest_api_calls ?? []).map((n: any) => <div key={n.id} className="flex gap-3 px-4 py-2"><Badge tone={n.status >= 400 ? "bad" : "ok"}>{n.status}</Badge><span>{n.method}</span><span className="truncate">{n.url}</span><span className="ml-auto text-muted">{fmtMs(n.duration_ms)}</span></div>)}
          {(c.performance?.longest_waits ?? []).map((w: any) => <div key={w.step_id} className="flex gap-3 px-4 py-2"><span>wait</span><span>{w.flow} · step {w.step_seq}</span><span className="ml-auto text-muted">{fmtMs(w.settle_ms)}</span></div>)}
        </Card>
      </Section>

      <Section title="Recommendations">
        {(c.recommendations ?? []).length === 0 && <div className="text-sm text-muted">Recommendations: {c.recommendations_status}.</div>}
        {(c.recommendations ?? []).map((r: any, i: number) => (
          <Card key={i} className="space-y-1 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2"><Badge tone="violet">{r.category}</Badge><Badge>{r.confidence} confidence</Badge><Badge>effort {r.effort}</Badge></div>
            <div className="font-medium">{r.text}</div><div className="text-muted">{r.rationale}</div>
            <div className="flex flex-wrap gap-1 pt-1">{(r.evidence_finding_ids ?? []).map((id: string) => <Link key={id} href={`/apps/${slug}/runs/${runId}?tab=findings`} className="font-mono text-[11px] text-accent hover:underline">{id}</Link>)}</div>
          </Card>
        ))}
        {(c.recommendations_dropped ?? []).length > 0 && <div className="text-xs text-muted">{c.recommendations_dropped.length} ungrounded recommendation(s) were dropped.</div>}
      </Section>

      <Section title="Test-quality notes">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          <li>{c.test_quality?.escalations} escalation(s) to Claude</li>
          <li>{(c.test_quality?.low_confidence_decisions ?? []).length} low-confidence decision(s)</li>
          <li>{c.test_quality?.judged_findings} judged finding(s); {c.test_quality?.checks_run} checks run; {c.test_quality?.divergences} divergence(s)</li>
        </ul>
      </Section>
      <div className="font-mono text-[11px] text-muted">playbook hash {c.integrity?.playbook_hash} · manifest hash {c.integrity?.manifest_hash}</div>
    </div>
  );
}

const Section = ({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) => (
  <section className="space-y-2"><div className="flex items-center"><h3 className="text-xs font-medium uppercase tracking-wide text-muted">{title}</h3><span className="ml-auto">{action}</span></div>{children}</section>
);
