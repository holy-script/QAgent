"use client";
import { ChevronLeft, ClipboardCopy, Download } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { BugReportView } from "@/components/live/bug-report";
import { NeedsApi } from "@/components/live/needs-api";
import { Badge, Button, Card, ErrorState, Loading, ago, type Tone } from "@/components/ui";
import { API_URL, USE_MOCK } from "@/lib/api/client";
import { useIssue, useIssueReport } from "@/lib/api/live";
import { ISSUE_STATUS } from "@/lib/terms";
import { toast } from "sonner";

const TONE: Record<string, Tone> = { open: "bad", regressed: "warn", resolved: "ok" };

export default function IssuePage() {
  const { slug, issueId } = useParams<{ slug: string; issueId: string }>();
  const { data: issue, error, isPending, refetch } = useIssue(issueId);
  const { data: report, error: reportError } = useIssueReport(issueId);
  const [copied, setCopied] = useState(false);
  if (USE_MOCK) return <NeedsApi what="Issues" />;
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;

  const exportUrl = (fmt: string) => `${API_URL}/reports/${report!.id}/export?format=${fmt}`;
  const copy = async () => {
    await navigator.clipboard.writeText(await (await fetch(exportUrl("md"), { credentials: "include" })).text());
    setCopied(true);
    toast.success("Copied. Paste it into your issue tracker.");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Link href={`/apps/${slug}/issues`} className="text-muted-foreground hover:text-foreground" aria-label="Back to all bugs"><ChevronLeft className="size-5" /></Link>
          <h2 className="min-w-0 flex-1 text-lg font-medium">{issue.title}</h2>
          <Badge tone={TONE[issue.status]} title={ISSUE_STATUS[issue.status]?.hint}>{ISSUE_STATUS[issue.status]?.label ?? issue.status}</Badge>
        </div>
        {report && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={copy}><ClipboardCopy className="size-4" />{copied ? "Copied" : "Copy for my issue tracker"}</Button>
            {(["md", "html", "pdf"] as const).map((f) => (
              <a key={f} href={exportUrl(f)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/[0.03] px-3.5 py-2 text-sm hover:bg-foreground/[0.06]">
                <Download className="size-4" />{f.toUpperCase()}
              </a>
            ))}
          </div>
        )}
        {report ? <BugReportView content={report.content ?? {}} slug={slug} /> : (
          <Card className="p-5 text-sm text-muted-foreground">{reportError ? "No write-up has been generated for this bug yet." : "Loading report…"}</Card>
        )}
      </div>
      <aside className="space-y-3">
        <h3 className="text-sm font-medium">Runs that found it</h3>
        {(issue.occurrence_list ?? []).map((o) => (
          <Link key={o.finding_id} href={`/apps/${slug}/runs/${o.run_id}?tab=findings`}>
            <Card className="p-3 text-sm transition hover:border-brand/50">
              <div className="font-mono text-xs text-muted-foreground">{o.run_id.slice(0, 8)}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">step {o.step_seq} · {o.started_at ? ago(o.started_at) : ""}</div>
            </Card>
          </Link>
        ))}
        {issue.status === "resolved" && issue.last_pass_run_id && <div className="text-xs text-ok">Fixed: a later run no longer found it (run {issue.last_pass_run_id.slice(0, 8)})</div>}
        <dl className="space-y-1 text-xs text-muted-foreground">
          <div>Check that failed <span className="font-mono text-foreground">{issue.check_key}</span></div>
          <div>Journey <span className="font-mono text-foreground">{issue.flow_key}</span></div>
          {(issue.requirement_keys ?? []).length > 0 && <div>Requirements: {(issue.requirement_keys ?? []).join(", ")}</div>}
        </dl>
      </aside>
    </div>
  );
}
