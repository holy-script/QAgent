"use client";
import { Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, cn } from "@/components/ui";
import { usePlaybooks, useStartRun } from "@/lib/api/hooks";
import type { Mode } from "@/lib/api/types";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "hybrid", label: "Hybrid", hint: "Jev decides, Claude on escalation" },
  { id: "baseline", label: "Baseline", hint: "Claude on every step" },
  { id: "stub", label: "Stub", hint: "No models, scripted" },
];

export function RunLauncher({ slug }: { slug: string }) {
  const router = useRouter();
  const { data: pbs } = usePlaybooks(slug);
  const start = useStartRun(slug);
  const [mode, setMode] = useState<Mode>("hybrid");
  const [pick, setPick] = useState<string>();
  const confirmed = pbs?.filter((p) => p.status === "confirmed") ?? [];
  const pb = confirmed.find((p) => p.id === pick) ?? confirmed[0];

  return (
    <Card className="space-y-4 p-5">
      <div className="font-medium">Start a run</div>
      {!pbs ? (
        <p className="text-sm text-muted">Loading playbooks…</p>
      ) : !pb ? (
        <p className="text-sm text-muted">Confirm a playbook first. Draft playbooks can&apos;t be run.</p>
      ) : (
        <>
          <select aria-label="Playbook" value={pb.id} onChange={(e) => setPick(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
            {confirmed.map((p) => <option key={p.id} value={p.id}>{p.name} (v{p.versions[0].version_no})</option>)}
          </select>
          <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Mode">
            {MODES.map((m) => (
              <button key={m.id} role="radio" aria-checked={mode === m.id} onClick={() => setMode(m.id)}
                className={cn("rounded-lg border p-2.5 text-left transition", mode === m.id ? "border-accent bg-accent/10" : "border-line hover:bg-white/5")}>
                <div className="text-sm font-medium">{m.label}</div>
                <div className="text-xs text-muted">{m.hint}</div>
              </button>
            ))}
          </div>
          {start.error && <p role="alert" className="text-sm text-bad">{start.error.message}</p>}
          <Button variant="primary" className="w-full" disabled={start.isPending}
            onClick={async () => { const r = await start.mutateAsync({ versionId: pb.current_version_id, mode }); router.push(`/apps/${slug}/runs/${r.id}`); }}>
            <Play className="size-4" />{start.isPending ? "Starting…" : "Run now"}
          </Button>
        </>
      )}
    </Card>
  );
}
