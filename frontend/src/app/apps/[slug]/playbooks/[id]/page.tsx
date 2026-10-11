"use client";
import { AlertCircle, AlertTriangle, CheckCircle2, History } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, ErrorState, Loading, SeverityBadge, StatusPill, ago, cn, inputCls } from "@/components/ui";
import { useConfirmPlaybook, usePlaybook, useSavePlaybook } from "@/lib/api/hooks";
import type { PlaybookVersion } from "@/lib/api/types";
import { PlaybookEditor } from "@/components/live/playbook-editor";
import { USE_MOCK } from "@/lib/api/client";
import type { Validation } from "@/lib/api/live";

export default function ReviewPlaybook() {
  const { slug, id } = useParams<{ slug: string; id: string }>();
  const { data: pb, error, isPending, refetch } = usePlaybook(id);
  const save = useSavePlaybook(slug);
  const confirm = useConfirmPlaybook(slug);
  const [sel, setSel] = useState<string>();
  const [draft, setDraft] = useState<string | null>(null);
  const [validation, setValidation] = useState<Validation>();
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;

  const v = pb.versions.find((x) => x.id === sel) ?? pb.versions[0];
  const isCurrent = v.id === pb.current_version_id;
  const errors = v.warnings.filter((w) => w.level === "error");

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-medium">{pb.name}</h2>
          <StatusPill status={isCurrent ? pb.status : "draft"} />
          <Badge>v{v.version_no}</Badge>
          <div className="ml-auto flex gap-2">
            {draft === null ? <Button onClick={() => setDraft(v.raw_markdown)}>Edit</Button> : (
              <>
                <Button onClick={() => setDraft(null)}>Discard</Button>
                <Button variant="primary" disabled={save.isPending || draft === v.raw_markdown || (validation?.errors?.length ?? 0) > 0}
                  onClick={() => save.mutate({ markdown: draft, playbookId: pb.id }, { onSuccess: () => { setDraft(null); setSel(undefined); } })}>
                  Save as v{pb.versions.length + 1}
                </Button>
              </>
            )}
            <Button variant="primary" disabled={!isCurrent || pb.status === "confirmed" || errors.length > 0 || confirm.isPending || draft !== null}
              title={errors.length ? "Fix parse errors first" : undefined} onClick={() => confirm.mutate(pb.id)}>
              <CheckCircle2 className="size-4" />Confirm
            </Button>
          </div>
        </div>

        {save.error && <p role="alert" className="whitespace-pre-line text-sm text-bad">{save.error.message}</p>}

        {v.warnings.length > 0 && (
          <Card className="divide-y divide-line">
            {v.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 px-4 py-2 text-sm">
                {w.level === "error" ? <AlertCircle className="mt-0.5 size-4 shrink-0 text-bad" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />}
                {w.line > 0 && <span className="text-muted">Line {w.line}</span>}<span>{w.message}</span>
              </div>
            ))}
          </Card>
        )}

        <div className="grid gap-4 xl:grid-cols-2">
          <Card className={cn("overflow-hidden", draft !== null && !USE_MOCK && "xl:col-span-2")}>
            <div className="border-b border-line px-4 py-2 text-xs uppercase tracking-wide text-muted">{draft === null ? "Markdown" : "Editing"}</div>
            {draft !== null && !USE_MOCK ? (
              <div className="p-3"><PlaybookEditor value={draft} onChange={setDraft} slug={slug} onValidation={setValidation} /></div>
            ) : draft !== null ? (
              <textarea aria-label="Edit Markdown" className={cn(inputCls, "h-[32rem] rounded-none border-0 font-mono text-xs")} value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false} />
            ) : (
              <pre className="max-h-[32rem] overflow-auto py-2 font-mono text-xs leading-5">
                {v.raw_markdown.split("\n").map((line, i) => {
                  const w = v.warnings.filter((x) => x.line === i + 1);
                  const bad = w.some((x) => x.level === "error");
                  return (
                    <div key={i} className={cn(w.length > 0 && (bad ? "bg-bad/10" : "bg-warn/10"))}>
                      <div className="flex"><span className="w-10 shrink-0 select-none pr-3 text-right text-muted/60">{i + 1}</span><code className="whitespace-pre-wrap break-all">{line || " "}</code></div>
                      {w.map((x, k) => <div key={k} className={cn("pl-10 text-[11px]", bad ? "text-bad" : "text-warn")}>↳ {x.message}</div>)}
                    </div>
                  );
                })}
              </pre>
            )}
          </Card>
          <div className="space-y-3">
            <div className="text-xs uppercase tracking-wide text-muted">Parsed · {v.parsed.flows.length} flows{v.parsed.base_url && ` · ${v.parsed.base_url}`}</div>
            {!v.parsed.flows.length && <Card className="p-4 text-sm text-muted">No flows parsed yet.</Card>}
            {v.parsed.flows.map((f) => (
              <Card key={f.key} className="space-y-3 p-4 text-sm">
                <div className="flex items-center gap-2"><span className="font-medium">{f.key}</span><SeverityBadge severity={f.severity} /></div>
                <List title="Steps" items={f.steps} ordered />
                <List title="Expect" items={f.expect} />
                {f.formulas.map((fo) => (
                  <div key={fo.name}><div className="text-xs text-muted">Formula · {fo.name} · {fo.source}</div><code className="mt-1 block rounded bg-black/30 p-2 text-xs">{fo.expr}</code></div>
                ))}
                <List title="Edge cases" items={f.edge_cases} />
              </Card>
            ))}
          </div>
        </div>
      </div>
      <aside className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium"><History className="size-4" />Versions</div>
        {pb.versions.map((x: PlaybookVersion) => (
          <button key={x.id} onClick={() => { setSel(x.id); setDraft(null); }}
            className={cn("w-full rounded-lg border p-3 text-left text-sm transition", x.id === v.id ? "border-accent bg-accent/10" : "border-line hover:bg-white/5")}>
            <div className="flex items-center justify-between"><span>v{x.version_no}</span>{x.id === pb.current_version_id && <Badge tone="ok">current</Badge>}</div>
            <div className="mt-0.5 text-xs text-muted">{ago(x.created_at)} · {x.content_hash.slice(0, 7)}</div>
          </button>
        ))}
      </aside>
    </div>
  );
}

function List({ title, items, ordered }: { title: string; items: string[]; ordered?: boolean }) {
  if (!items.length) return null;
  const L = ordered ? "ol" : "ul";
  return (
    <div>
      <div className="text-xs text-muted">{title}</div>
      <L className={cn("mt-1 space-y-0.5 pl-5 text-sm", ordered ? "list-decimal" : "list-disc")}>{items.map((s, i) => <li key={i}>{s}</li>)}</L>
    </div>
  );
}
