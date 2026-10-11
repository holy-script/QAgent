"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Field, inputCls } from "@/components/ui";
import { useReplay } from "@/lib/api/live";

/** Re-run a finished run deterministically from its decision tape, optionally overriding gating and budgets. */
export function ReplayPanel({ slug, runId, onClose }: { slug: string; runId: string; onClose: () => void }) {
  const router = useRouter();
  const replay = useReplay();
  const [auto, setAuto] = useState("");
  const [esc, setEsc] = useState("");
  const [fallback, setFallback] = useState(false);
  const go = () => {
    const overrides: Record<string, unknown> = {};
    if (auto) overrides.gate_auto_min = Number(auto);
    if (esc) overrides.gate_escalate_min = Number(esc);
    if (fallback) overrides.live_fallback = true;
    replay.mutate({ runId, overrides }, { onSuccess: (r) => router.push(`/apps/${slug}/runs/${r.id}`) });
  };
  return (
    <Card className="space-y-4 p-5">
      <div>
        <div className="font-medium">Re-run from tape</div>
        <p className="text-sm text-muted">Every model answer comes from this run&apos;s recorded decisions, so the browser runs again against the app with the same choices. A divergence event is raised when a page no longer matches the recording.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Auto gate minimum" hint="Default 0.75"><input className={inputCls} inputMode="decimal" value={auto} onChange={(e) => setAuto(e.target.value)} placeholder="0.75" /></Field>
        <Field label="Escalate gate minimum" hint="Default 0.45"><input className={inputCls} inputMode="decimal" value={esc} onChange={(e) => setEsc(e.target.value)} placeholder="0.45" /></Field>
        <label className="flex items-start gap-2 pt-6 text-sm"><input type="checkbox" className="mt-1" checked={fallback} onChange={(e) => setFallback(e.target.checked)} />Use the live model for steps missing from the tape</label>
      </div>
      {replay.error && <p role="alert" className="text-sm text-bad">{replay.error.message}</p>}
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={go} disabled={replay.isPending}>{replay.isPending ? "Starting…" : "Start replay run"}</Button>
      </div>
    </Card>
  );
}
