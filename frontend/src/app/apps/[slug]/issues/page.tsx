"use client";
import { Bug } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { NeedsApi } from "@/components/live/needs-api";
import { Badge, Empty, ErrorState, Loading, SeverityBadge, ago, cn, type Tone } from "@/components/ui";
import { USE_MOCK } from "@/lib/api/client";
import { useIssues } from "@/lib/api/live";

const TONE: Record<string, Tone> = { open: "bad", regressed: "warn", resolved: "ok" };
const FILTERS = ["all", "open", "regressed", "resolved"] as const;

export default function Issues() {
  const { slug } = useParams<{ slug: string }>();
  const [status, setStatus] = useState<(typeof FILTERS)[number]>("all");
  const { data, error, isPending, refetch } = useIssues(slug, status === "all" ? undefined : status);
  if (USE_MOCK) return <NeedsApi what="Issues" />;
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-medium">Issues</h2>
        <div role="group" aria-label="Status" className="ml-auto flex overflow-hidden rounded-lg border border-line">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setStatus(f)} aria-pressed={status === f} className={cn("px-3 py-1.5 text-xs capitalize", status === f ? "bg-accent/20 text-accent" : "text-muted hover:bg-white/5")}>{f}</button>
          ))}
        </div>
      </div>
      {!data.length ? (
        <Empty icon={<Bug className="size-8" />} title="No issues" hint="Issues open when a run finds a bug and resolve when a later run no longer reproduces it." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-muted">
              <tr>{["Issue", "Status", "Severity", "Flow", "Check", "Seen", "Updated"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((i) => (
                <tr key={i.id} className="hover:bg-white/[0.03]">
                  <td className="max-w-md px-4 py-2.5"><Link href={`/apps/${slug}/issues/${i.id}`} className="font-medium hover:text-accent">{i.title}</Link></td>
                  <td className="px-4 py-2.5"><Badge tone={TONE[i.status]}>{i.status}</Badge></td>
                  <td className="px-4 py-2.5"><SeverityBadge severity={i.severity} /></td>
                  <td className="px-4 py-2.5 font-mono text-xs">{i.flow_key}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{i.check_key}</td>
                  <td className="px-4 py-2.5 tabular-nums">{i.occurrences}×</td>
                  <td className="px-4 py-2.5 text-xs text-muted">{i.updated_at ? ago(i.updated_at) : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
