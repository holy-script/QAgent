"use client";
import { Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, SelectField, cn } from "@/components/ui";
import { usePlaybooks, useStartRun } from "@/lib/api/hooks";
import type { Mode } from "@/lib/api/types";
import { MODE_INFO } from "@/lib/terms";

const MODES = (Object.keys(MODE_INFO) as Mode[]).map((id) => ({ id, ...MODE_INFO[id] }));

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
                className={cn("rounded-lg border p-2.5 text-left transition", mode === m.id ? "border-brand bg-brand/10" : "border-border hover:bg-foreground/5")}>
                <div className="text-sm font-medium">{m.label}{m.id === "hybrid" && <span className="ml-1.5 text-xs font-normal text-brand">recommended</span>}</div>
                <div className="text-xs leading-snug text-muted-foreground">{m.hint}</div>
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
