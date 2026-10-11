"use client";
/* eslint-disable @next/next/no-img-element, @typescript-eslint/no-explicit-any */
import Link from "next/link";
import { Badge, Card, SeverityBadge, cn, fmtMs } from "@/components/ui";
import { CallBodies } from "@/components/live/call-bodies";
import { API_URL } from "@/lib/api/client";
import { useState } from "react";

const img = (id?: string | null) => (id ? `${API_URL}/api/artifacts/${id}/content` : "");

/** Renders a stored bug report (assembled by the backend from recorded facts; only impact/cause are model prose). */
export function BugReportView({ content, slug }: { content: Record<string, any>; slug: string }) {
  const [call, setCall] = useState<string | null>(null);
  const items: any[] = content.evidence?.items ?? [];
  const shots = ["annotated", "screenshot_before", "screenshot_after"].map((k) => items.find((e) => e.kind === k && e.available)).filter(Boolean);
  const [shot, setShot] = useState(0);
  const n = content.narrative ?? {};
  const env = content.environment ?? {};
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <SeverityBadge severity={content.severity} />
        <Badge>priority: {content.priority}</Badge>
        {content.judged_by !== "code" && <Badge tone="warn">judged by AI ({content.judged_by}); severity capped at medium</Badge>}
        <span className="text-muted-foreground">
          Found in {content.reproducibility?.seen_in} of the last {content.reproducibility?.of_last} runs
        </span>
      </div>

      <Section title="Requirements affected">
        {(content.violated_requirements ?? []).length === 0 && <div className="text-sm text-muted-foreground">This problem is not linked to a requirement.</div>}
        {(content.violated_requirements ?? []).map((r: any) => (
          <Card key={r.key} className="p-3 text-sm">
            <div className="flex items-center gap-2"><Badge tone="accent">{r.key}</Badge><span className="font-medium">{r.title}</span><span className="ml-auto text-xs text-muted-foreground">{r.prd_ref}</span></div>
            <div className="mt-1 text-muted-foreground">{r.acceptance}</div>
          </Card>
        ))}
      </Section>

      <Section title="Steps to reproduce">
        <ol className="space-y-1 text-sm">{(content.steps_to_reproduce ?? []).map((s: string, i: number) => <li key={i} className="font-mono text-xs">{s}</li>)}</ol>
      </Section>

      <Section title="What should happen vs what happened">
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <div><div className="text-xs text-muted-foreground">What should happen</div><div className="font-mono text-ok">{content.expected_actual?.expected}</div></div>
          <div><div className="text-xs text-muted-foreground">What happened</div><div className="break-words font-mono text-bad">{content.expected_actual?.actual}</div></div>
        </div>
        {(content.expected_actual?.inputs ?? []).length > 0 && (
          <Card className="mt-3 divide-y divide-border text-sm">
            {content.expected_actual.inputs.map((i: any) => (
              <div key={i.name} className="flex flex-wrap items-center gap-x-3 px-3 py-2">
                <span className="font-mono text-xs text-brand">{i.name}</span>
                <span className="font-mono text-xs">{JSON.stringify(i.value ?? i.values ?? i.status)}</span>
                {i.source && <span className="font-mono text-[11px] text-muted-foreground">from {i.source}{i.url ? ` (${i.url})` : ""}</span>}
                {i.call_id && <button className="text-[11px] text-brand hover:underline" onClick={() => setCall(i.call_id)}>see the server call</button>}
              </div>
            ))}
          </Card>
        )}
      </Section>

      <Section title="Proof">
        {shots.length > 0 && (
          <>
            <div className="mb-2 flex gap-1">
              {shots.map((e: any, i: number) => (
                <button key={e.id} onClick={() => setShot(i)} className={cn("rounded-md border px-2.5 py-1 text-xs", shot === i ? "border-brand bg-brand/10 text-brand" : "border-border text-muted-foreground hover:bg-foreground/5")}>
                  {e.kind === "annotated" ? "Annotated" : e.kind === "screenshot_before" ? "Before" : "After"}
                </button>
              ))}
            </div>
            <img src={img((shots[shot] as any).artifact_id)} alt="Evidence screenshot" className="w-full max-w-3xl rounded-lg border border-border" />
          </>
        )}
        {(content.evidence?.network_calls ?? []).map((c: any) => (
          <Card key={c.evidence_id} className="mt-2 p-3 font-mono text-xs">
            <button className="flex w-full items-center gap-2 text-left" onClick={() => setCall(call === c.id ? null : c.id)}>
              <Badge tone={c.status >= 400 ? "bad" : "ok"}>{c.status}</Badge><span>{c.method}</span><span className="truncate">{c.url}</span><span className="ml-auto text-muted-foreground">{fmtMs(c.duration_ms)}</span>
            </button>
          </Card>
        ))}
        {call && <Card className="mt-2 p-3"><CallBodies callId={call} /></Card>}
        <div className="mt-2 flex flex-wrap gap-3 text-sm">
          {env.run_id && content.evidence?.flow_key && (
            <Link className="text-brand hover:underline" href={`/apps/${slug}/runs/${env.run_id}?tab=flows&step=${encodeURIComponent(content.evidence.flow_key)}:${content.evidence.step_seq}`}>Open the step in the run viewer →</Link>
          )}
        </div>
      </Section>

      <Section title="Where it was found">
        <dl className="grid grid-cols-[10rem_1fr] gap-y-1 text-sm">
          {Object.entries(env).map(([k, v]) => (<><dt key={k} className="text-muted-foreground">{k}</dt><dd key={k + "v"} className="break-all font-mono text-xs">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></>))}
        </dl>
      </Section>

      <Section title="Why it matters">
        <p className="text-sm">{n.impact ?? "Not generated."}</p>
      </Section>
      <Section title="Possible cause (an AI guess)">
        <p className="text-sm">{n.suspected_cause ?? "Not generated."}</p>
        {n.status && n.status !== "generated" && <p className="mt-1 text-xs text-muted-foreground">AI write-up status: {n.status}</p>}
      </Section>
    </div>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2"><h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>{children}</section>
);
