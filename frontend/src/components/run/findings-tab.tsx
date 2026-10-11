"use client";
import { Bug } from "lucide-react";
import { Badge, Card, Empty, SeverityBadge } from "@/components/ui";
import type { RunView } from "@/lib/run-state";

const ORDER = ["critical", "high", "medium", "low"];

export function FindingsTab({ view, onOpen }: { view: RunView; onOpen: (flow: string, seq: number) => void }) {
  if (!view.findings.length) {
    return <Empty icon={<Bug className="size-8" />} title={view.done ? "No findings" : "No findings so far"} hint={view.done ? "Every check passed in this run." : "Findings appear as verification checks fail."} />;
  }
  const rows = [...view.findings].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {rows.map((f) => (
        <Card key={f.id} className="slide-in space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={f.severity} /><Badge tone="violet">{f.kind}</Badge>
            <button className="ml-auto text-xs text-accent hover:underline" onClick={() => onOpen(f.flow_key, f.step_seq)}>{f.flow_key} · step {f.step_seq} →</button>
          </div>
          <div className="font-medium">{f.title}</div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-xs text-muted">Expected</div><div className="font-mono text-ok">{f.expected}</div></div>
            <div><div className="text-xs text-muted">Actual</div><div className="font-mono text-bad">{f.actual}</div></div>
          </div>
          <details className="text-xs text-muted"><summary className="cursor-pointer">Evidence</summary>
            <pre className="mt-2 overflow-auto rounded bg-black/40 p-2">{JSON.stringify(f.evidence, null, 2)}</pre></details>
        </Card>
      ))}
    </div>
  );
}
