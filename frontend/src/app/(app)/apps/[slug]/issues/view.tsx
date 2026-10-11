"use client";
import { SimpleTable, TableCell, TableRow } from "@/components/ui";
import { Bug } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Badge, Empty, ErrorState, Loading, SeverityBadge, ago, cn, type Tone } from "@/components/ui";
import { useIssues } from "@/lib/api/live";
import { ISSUE_STATUS } from "@/lib/terms";

const TONE: Record<string, Tone> = { open: "bad", regressed: "warn", resolved: "ok" };
const FILTERS = ["all", "open", "regressed", "resolved"] as const;
const FILTER_LABEL: Record<string, string> = { all: "All", open: "Open", regressed: "Came back", resolved: "Fixed" };

export default function Issues() {
  const { slug } = useParams<{ slug: string }>();
  const [status, setStatus] = useState<(typeof FILTERS)[number]>("all");
  const { data, error, isPending, refetch } = useIssues(slug, status === "all" ? undefined : status);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div><h2 className="font-medium">Bugs found</h2><p className="text-sm text-muted-foreground">Every problem a run finds becomes a bug. The same problem across runs is one bug, marked Fixed once a later run no longer finds it.</p></div>
        <div role="group" aria-label="Status" className="ml-auto flex overflow-hidden rounded-lg border border-border">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setStatus(f)} aria-pressed={status === f} className={cn("px-3 py-1.5 text-xs", status === f ? "bg-brand/15 text-brand" : "text-muted-foreground hover:bg-foreground/5")}>{FILTER_LABEL[f]}</button>
          ))}
        </div>
      </div>
      {!data.length ? (
        <Empty icon={<Bug className="size-8" />} title="No bugs found" hint="Nothing has gone wrong in your runs so far. Bugs appear here the first time a run finds a problem." />
      ) : (
        <SimpleTable head={["Bug", "Status", "How serious", "Journey", "Check", "Found in", "Updated"]}>
              {data.map((i) => (
                <TableRow key={i.id} className="hover:bg-foreground/[0.03]">
                  <TableCell className="max-w-md px-4 py-2.5"><Link href={`/apps/${slug}/issues/${i.id}`} className="font-medium hover:text-brand">{i.title}</Link></TableCell>
                  <TableCell className="px-4 py-2.5"><Badge tone={TONE[i.status]} title={ISSUE_STATUS[i.status]?.hint}>{ISSUE_STATUS[i.status]?.label ?? i.status}</Badge></TableCell>
                  <TableCell className="px-4 py-2.5"><SeverityBadge severity={i.severity} /></TableCell>
                  <TableCell className="px-4 py-2.5 font-mono text-xs">{i.flow_key}</TableCell>
                  <TableCell className="px-4 py-2.5 font-mono text-xs">{i.check_key}</TableCell>
                  <TableCell className="px-4 py-2.5 tabular-nums">{i.occurrences} run{i.occurrences === 1 ? "" : "s"}</TableCell>
                  <TableCell className="px-4 py-2.5 text-xs text-muted-foreground">{i.updated_at ? ago(i.updated_at) : "–"}</TableCell>
                </TableRow>
              ))}
      </SimpleTable>
      )}
    </div>
  );
}
