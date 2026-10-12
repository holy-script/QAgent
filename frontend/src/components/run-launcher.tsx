"use client";
import { Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, SelectField, cn } from "@/components/ui";
import { Checkbox } from "@/components/ui/checkbox";
import { usePlaybooks, useStartRun } from "@/lib/api/hooks";
import type { Mode } from "@/lib/api/types";
import { MODE_INFO } from "@/lib/terms";

const MODES = (Object.keys(MODE_INFO) as Mode[]).map((id) => ({ id, ...MODE_INFO[id] }));

export function RunLauncher({ slug }: { slug: string }) {
  const router = useRouter();
  const { data: pbs } = usePlaybooks(slug);
  const start = useStartRun(slug);
  const [mode, setMode] = useState<Mode>("hybrid");
  const [plan, setPlan] = useState(false);
  const [pick, setPick] = useState<string>();
  const confirmed = pbs?.filter((p) => p.status === "confirmed") ?? [];
  const pb = confirmed.find((p) => p.id === pick) ?? confirmed[0];

  return (
    <Card className="space-y-4 p-5" data-tour="run-launcher">
      <div><div className="font-medium">Run a test</div><p className="text-sm text-muted-foreground">QAgent opens a browser and works through your test plan. This usually takes under a minute.</p></div>
      {!pbs ? (
        <p className="text-sm text-muted-foreground">Loading your test plans…</p>
      ) : !pb ? (
        <p className="text-sm text-muted-foreground">You need a test plan first. A test plan says what to check. Open the Test plans tab to add one.</p>
      ) : (
        <>
          <SelectField label="Test plan" value={pb.id} onChange={setPick}
            options={confirmed.map((p) => ({ value: p.id, label: `${p.name} (version ${p.versions[0].version_no})` }))} />
          <div className="grid gap-2" role="radiogroup" aria-label="How should decisions be made?">
            {MODES.map((m) => (
              <button key={m.id} role="radio" aria-checked={mode === m.id} onClick={() => setMode(m.id)}
                className={cn("rounded-lg border p-2.5 text-left transition", mode === m.id ? "border-brand bg-brand/10" : "border-border hover:bg-secondary")}>
                <div className="text-sm font-medium">{m.label}{m.id === "hybrid" && <span className="ml-1.5 text-xs font-normal text-brand">recommended</span>}</div>
                <div className="text-xs leading-snug text-muted-foreground">{m.hint}</div>
              </button>
            ))}
          </div>
          {mode !== "stub" && (
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={plan} onCheckedChange={(v) => setPlan(v === true)} className="mt-0.5" />
              <span>Let the strong AI plan each journey first<span className="block text-xs text-muted-foreground">It reads the steps and writes a short note for each one. Slightly slower and a little extra cost; it can help with unclear steps.</span></span>
            </label>
          )}
          {start.error && <p role="alert" className="text-sm text-bad">{start.error.message}</p>}
          <Button variant="primary" className="w-full" disabled={start.isPending}
            onClick={async () => { const r = await start.mutateAsync({ versionId: pb.current_version_id, mode, plan: plan && mode !== "stub" }); router.push(`/apps/${slug}/runs/${r.id}${new URLSearchParams(window.location.search).get("guide") === "run" ? "?guide=results" : ""}`); }}>
            <Play className="size-4" />{start.isPending ? "Starting…" : "Run now"}
          </Button>
        </>
      )}
    </Card>
  );
}
