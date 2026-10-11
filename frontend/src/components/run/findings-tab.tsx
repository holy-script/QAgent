"use client";
import { FINDING_KIND } from "@/lib/terms";
import { Bug } from "lucide-react";
import { useState } from "react";
import { Badge, Card, Empty, SeverityBadge } from "@/components/ui";
import { EvidencePanel } from "@/components/live/evidence-panel";
import { USE_MOCK } from "@/lib/api/client";
import type { RunView } from "@/lib/run-state";

const ORDER = ["critical", "high", "medium", "low"];

export function FindingsTab({ view, onOpen, slug }: { view: RunView; onOpen: (flow: string, seq: number) => void; slug: string }) {
  const [evidence, setEvidence] = useState<string | null>(null);
  if (!view.findings.length) {
    return <Empty icon={<Bug className="size-8" />} title={view.done ? "No problems found" : "No problems so far"} hint={view.done ? "Every check passed in this run." : "A problem appears here the moment a check fails."} />;
  }
  const rows = [...view.findings].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {rows.map((f) => (
        <Card key={f.id} className="slide-in space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={f.severity} /><Badge tone="violet">{FINDING_KIND[f.kind] ?? f.kind}</Badge>
            <button className="ml-auto text-xs text-brand hover:underline" onClick={() => onOpen(f.flow_key, f.step_seq)}>{f.flow_key} · step {f.step_seq} →</button>
          </div>
          <div className="font-medium">{f.title}</div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-xs text-muted-foreground">What should happen</div><div className="font-mono text-ok">{f.expected}</div></div>
            <div><div className="text-xs text-muted-foreground">What happened</div><div className="font-mono text-bad">{f.actual}</div></div>
          </div>
          {USE_MOCK ? (
            <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Proof</summary>
              <pre className="mt-2 overflow-auto rounded bg-code p-2">{JSON.stringify(f.evidence, null, 2)}</pre></details>
          ) : <button className="text-xs text-brand hover:underline" onClick={() => setEvidence(f.id)}>See the proof →</button>}
        </Card>
      ))}
    {evidence && <EvidencePanel findingId={evidence} slug={slug} onClose={() => setEvidence(null)} />}
    </div>
  );
}
