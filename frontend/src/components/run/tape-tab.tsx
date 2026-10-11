"use client";
import { Brain, ClipboardList, FileText, Footprints, Scale } from "lucide-react";
import { Badge, Card, Empty, ErrorState, Loading, fmtMs, fmtUsd } from "@/components/ui";
import { useTape, type TapeEntry } from "@/lib/api/live";

const KINDS: Record<string, { label: string; icon: typeof Brain; hint: string }> = {
  planner: { label: "Plan", icon: ClipboardList, hint: "The strong AI read the steps before the journey ran." },
  decision: { label: "Steps", icon: Footprints, hint: "Each step: which element to use." },
  judge: { label: "Checks", icon: Scale, hint: "Yes/no questions about what the page shows." },
  report: { label: "Report", icon: FileText, hint: "Writing the run report." },
  bug_narrative: { label: "Bug write-ups", icon: FileText, hint: "Impact and likely cause for each bug." },
};
const SECTIONS = ["planner", "decision", "judge", "bug_narrative", "report"];
const who = (d: string) => (d === "claude" ? "strong AI" : d === "jev" ? "fast AI" : d === "replay" ? "recording" : d || "rules");

function Row({ e }: { e: TapeEntry }) {
  const conf = e.confidence ?? null;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border px-4 py-2 text-sm first:border-t-0">
      <span className="w-24 shrink-0 text-xs text-muted-foreground">{e.flow_key ? `${e.flow_key}${e.step_seq ? ` · step ${e.step_seq}` : ""}` : "whole run"}</span>
      <span className="min-w-0 flex-1 truncate" title={e.label}>{e.label}{e.outcome && <span className="text-muted-foreground"> → {e.outcome}</span>}</span>
      <Badge tone={e.decider === "claude" ? "violet" : "neutral"}>{who(e.decider)}</Badge>
      {e.replayed && <Badge tone="ok">from recording</Badge>}
      {e.branch === "ESCALATE" && <Badge tone="warn">double-checked</Badge>}
      {conf !== null && <span className="w-12 text-right text-xs tabular-nums text-muted-foreground" title="Confidence">{Math.round(conf * 100)}%</span>}
      <span className="w-14 text-right text-xs tabular-nums text-muted-foreground">{e.latency_ms ? fmtMs(e.latency_ms) : "–"}</span>
      <span className="w-16 text-right text-xs tabular-nums text-muted-foreground">{e.cost_usd ? fmtUsd(e.cost_usd) : "free"}</span>
    </li>
  );
}

/** Every AI call of the run, in the order it happened, with what each cost. Repeating a run replays this list. */
export function TapeTab({ runId }: { runId: string }) {
  const { data, error, isPending, refetch } = useTape(runId);
  if (isPending) return <Loading label="Loading AI calls…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  if (!data.length) return <Empty title="No AI calls recorded" hint="Practice runs use simple rules instead of AI, so there is nothing to list." />;
  const total = data.reduce((a, e) => a + e.cost_usd, 0);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {SECTIONS.map((k) => {
          const rows = data.filter((e) => e.kind === k);
          const I = KINDS[k].icon;
          return (
            <Card key={k} className="px-4 py-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><I className="size-3.5" />{KINDS[k].label}</div>
              <div className="mt-1 text-lg font-semibold tabular-nums">{rows.length}</div>
              <div className="text-xs text-muted-foreground">{fmtUsd(rows.reduce((a, e) => a + e.cost_usd, 0))}</div>
            </Card>
          );
        })}
      </div>
      <p className="text-sm text-muted-foreground">{data.length} AI calls, {fmtUsd(total)} in total. “Repeat exactly” answers all of these from this list instead of asking the AI again.</p>
      {SECTIONS.map((k) => {
        const rows = data.filter((e) => e.kind === k);
        if (!rows.length) return null;
        return (
          <section key={k} aria-label={KINDS[k].label}>
            <h3 className="mb-1.5 flex items-baseline gap-2 text-sm font-medium">{KINDS[k].label}<span className="text-xs font-normal text-muted-foreground">{KINDS[k].hint}</span></h3>
            <Card className="overflow-hidden p-0"><ul>{rows.map((e, i) => <Row key={i} e={e} />)}</ul></Card>
          </section>
        );
      })}
    </div>
  );
}
