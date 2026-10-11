"use client";
/* eslint-disable @next/next/no-img-element */
import { X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Card, ErrorState, Loading, SeverityBadge, cn, fmtMs } from "@/components/ui";
import { CallBodies } from "@/components/live/call-bodies";
import { API_URL } from "@/lib/api/client";
import { useEvidence } from "@/lib/api/live";

const IMG_KINDS = ["annotated", "screenshot_after", "screenshot_before"] as const;
const LABEL: Record<string, string> = { annotated: "Annotated", screenshot_after: "After", screenshot_before: "Before" };

/** The evidence graph of one finding: what failed, the values the check read and where each came from, and the proof. */
export function EvidencePanel({ findingId, slug, onClose }: { findingId: string; slug: string; onClose: () => void }) {
  const { data, error, isPending, refetch } = useEvidence(findingId);
  const [shot, setShot] = useState<string>("annotated");
  const [openCall, setOpenCall] = useState<string | null>(null);
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const images = data ? IMG_KINDS.map((k) => data.evidence.find((e) => e.kind === k && e.available)).filter(Boolean) : [];
  const current = images.find((e) => e!.kind === shot) ?? images[0];
  const calls = data?.evidence.filter((e) => e.kind === "network_call" && e.call) ?? [];
  const waits = data?.evidence.filter((e) => e.kind === "wait_frame" && e.available) ?? [];
  const f = data?.finding;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <aside role="dialog" aria-label="Finding evidence" onClick={(e) => e.stopPropagation()}
        className="slide-in h-full w-full max-w-3xl space-y-5 overflow-y-auto border-l border-line bg-background p-5">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-xs text-muted">Evidence</div>
            <h3 className="text-lg font-medium">{f?.title ?? "Loading…"}</h3>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted hover:bg-white/10"><X className="size-5" /></button>
        </div>
        {isPending && <Loading />}
        {error && <ErrorState error={error} retry={refetch} />}
        {data && f && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <SeverityBadge severity={f.severity} /><Badge tone="violet">{f.kind}</Badge>
              <Badge>{f.check_key}</Badge>
              {f.judged_by !== "code" && <Badge tone="warn">judged by {f.judged_by}</Badge>}
              {f.requirement_keys.map((r) => <Badge key={r} tone="accent">{r}</Badge>)}
              {f.issue_id && <Link href={`/apps/${slug}/issues/${f.issue_id}`} className="ml-auto text-xs text-accent hover:underline">Open issue →</Link>}
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><div className="text-xs text-muted">Expected</div><div className="font-mono text-ok">{f.expected}</div></div>
              <div><div className="text-xs text-muted">Actual</div><div className="break-words font-mono text-bad">{f.actual}</div></div>
            </div>

            {current && (
              <section className="space-y-2">
                <div className="flex gap-1">
                  {images.map((e) => (
                    <button key={e!.id} onClick={() => setShot(e!.kind)}
                      className={cn("rounded-md border px-2.5 py-1 text-xs", current.kind === e!.kind ? "border-accent bg-accent/10 text-accent" : "border-line text-muted hover:bg-white/5")}>
                      {LABEL[e!.kind]}
                    </button>
                  ))}
                  <span className="ml-auto self-center text-xs text-muted">step {f.step_seq}</span>
                </div>
                <img src={`${API_URL}/api/artifacts/${current.artifact_id}/content`} alt={`${LABEL[current.kind]} screenshot`} className="w-full rounded-lg border border-line" />
              </section>
            )}
            {waits.length > 0 && (
              <section className="space-y-2">
                <h4 className="text-xs font-medium uppercase tracking-wide text-muted">Wait frames ({waits.length})</h4>
                <div className="flex gap-2 overflow-x-auto">{waits.map((w, i) => <img key={w.id} src={`${API_URL}/api/artifacts/${w.artifact_id}/content`} alt={`Wait frame ${i + 1}`} className="h-24 rounded border border-line" />)}</div>
              </section>
            )}

            {data.check_result && Object.keys(data.check_result.inputs).length > 0 && (
              <section className="space-y-2">
                <h4 className="text-xs font-medium uppercase tracking-wide text-muted">Check inputs and where each came from</h4>
                <Card className="divide-y divide-line text-sm">
                  {Object.entries(data.check_result.inputs).map(([name, src]) => {
                    const s = (typeof src === "object" && src ? src : { value: src }) as Record<string, unknown>;
                    return (
                      <div key={name} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                        <span className="font-mono text-xs text-accent">{name}</span>
                        <span className="font-mono text-xs">{JSON.stringify(s.value ?? s.values ?? s.status ?? s)}</span>
                        {typeof s.source === "string" && <span className="font-mono text-[11px] text-muted">from {s.source}</span>}
                        {typeof s.call_id === "string" && <button className="text-[11px] text-accent hover:underline" onClick={() => setOpenCall(s.call_id as string)}>recorded call</button>}
                      </div>
                    );
                  })}
                </Card>
              </section>
            )}

            {calls.length > 0 && (
              <section className="space-y-2">
                <h4 className="text-xs font-medium uppercase tracking-wide text-muted">Network calls ({calls.length})</h4>
                <Card className="divide-y divide-line">
                  {calls.map((e) => (
                    <div key={e.id} className="px-3 py-2">
                      <button className="flex w-full items-center gap-2 text-left font-mono text-xs" onClick={() => setOpenCall(openCall === e.call!.id ? null : e.call!.id)}>
                        <Badge tone={e.call!.status >= 400 ? "bad" : "ok"}>{e.call!.status}</Badge><span>{e.call!.method}</span>
                        <span className="truncate">{e.call!.url}</span><span className="ml-auto text-muted">{fmtMs(e.call!.duration_ms)}</span>
                      </button>
                      {openCall === e.call!.id && <div className="mt-2"><CallBodies callId={e.call!.id} /></div>}
                    </div>
                  ))}
                </Card>
              </section>
            )}
            {openCall && !calls.some((c) => c.call!.id === openCall) && <Card className="p-3"><CallBodies callId={openCall} /></Card>}

            {data.decisions.length > 0 && (
              <section className="space-y-1 text-xs text-muted">
                <h4 className="font-medium uppercase tracking-wide">Decisions that led here</h4>
                {data.decisions.map((d, i) => <div key={i}>{d.decider} chose {d.choice} at {(d.confidence * 100).toFixed(0)}% ({d.branch}){d.few_shot_ids.length ? ` · examples ${d.few_shot_ids.join(", ")}` : ""}</div>)}
              </section>
            )}
            <div className="font-mono text-[11px] text-muted">run {data.integrity.run_id} · playbook version {data.integrity.playbook_version_id} · fingerprint {f.fingerprint}</div>
          </>
        )}
      </aside>
    </div>
  );
}
