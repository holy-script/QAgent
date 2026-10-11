"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import { AlertCircle, AlertTriangle, CheckCircle2, Pencil, Plus, Sparkles, Trash2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Field, cn, inputCls } from "@/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useExtractPrd, useNormalize, useValidate, type Validation } from "@/lib/api/live";
import { MarkdownEditor, type Problem } from "@/components/live/markdown-editor";
import { CATEGORIES, FORMS, diffLines, insertItem, itemMarkdown, itemToValues, nextKey, removeItem, replaceItem, type Category, type FieldSpec } from "@/lib/playbook-md";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

/**
 * Category editor over the playbook Markdown: one tab per category with an add form and the existing items, live
 * validation (errors block saving, warnings do not), a coverage panel, and a raw Markdown view that stays in sync.
 */
export function PlaybookEditor({ value, onChange, slug, onValidation }: { value: string; onChange: (md: string) => void; slug: string; onValidation?: (v: Validation | undefined) => void }) {
  const [view, setView] = useState<"categories" | "raw">("categories");
  const [cat, setCat] = useState<Category>("requirement");
  const { data: v, isFetching } = useValidate(useDebounced(value, 400));
  useEffect(() => onValidation?.(v), [v, onValidation]);

  const items = useMemo(() => (v?.items ?? []) as { key: string; category: string; title: string; body: Record<string, any> }[], [v]);
  const counts = useMemo(() => Object.fromEntries(CATEGORIES.map((c) => [c.id, items.filter((i) => i.category === c.id).length])), [items]);
  const errors = useMemo(() => v?.errors ?? [], [v]);
  const warnings = useMemo(() => v?.warnings ?? [], [v]);
  const problems = useMemo<Problem[]>(() => [...errors.map((message) => ({ message, level: "error" as const })), ...warnings.map((message) => ({ message, level: "warning" as const }))], [errors, warnings]);
  const [editing, setEditing] = useState<string | null>(null);
  const uncovered = ((v?.coverage as any)?.uncovered ?? []) as string[];
  const flowKeys = items.filter((i) => i.category === "flow").map((i) => i.key);
  const [normalize, setNormalize] = useState<string | null>(null);
  const norm = useNormalize();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="How to edit" className="flex overflow-hidden rounded-lg border border-border">
          {(["categories", "raw"] as const).map((k) => (
            <button key={k} onClick={() => setView(k)} aria-pressed={view === k} className={cn("px-3 py-1.5 text-xs", view === k ? "bg-brand/20 text-brand" : "text-muted-foreground hover:bg-foreground/5")}>{k === "raw" ? "Text" : "Guided"}</button>
          ))}
        </div>
        <Button onClick={() => norm.mutate(value, { onSuccess: (r) => setNormalize(r.markdown) })} disabled={!value.trim() || norm.isPending} title="Paste rough notes, and AI rewrites them into a proper test plan. You review the changes before anything is replaced.">
          <Wand2 className="size-4" />{norm.isPending ? "Rewriting…" : "Rewrite my notes as a test plan"}
        </Button>
        <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          {isFetching ? "Validating…" : errors.length ? <><AlertCircle className="size-4 text-bad" />{errors.length} problem{errors.length > 1 ? "s" : ""} to fix</> : value.trim() ? <><CheckCircle2 className="size-4 text-ok" />Valid</> : null}
        </span>
      </div>
      {norm.error && <p role="alert" className="text-sm text-bad">{norm.error.message}</p>}

      {(errors.length > 0 || warnings.length > 0) && (
        <Card className="divide-y divide-border">
          {errors.map((m, i) => <Msg key={`e${i}`} level="error" text={m} />)}
          {warnings.map((m, i) => <Msg key={`w${i}`} level="warning" text={m} />)}
        </Card>
      )}

      {view === "raw" ? (
        <MarkdownEditor value={value} onChange={onChange} problems={problems} minHeight="30rem" maxHeight="40rem" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem]">
          <div className="min-w-0 space-y-4">
            <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-border">
              {CATEGORIES.map((c) => (
                <button key={c.id} role="tab" aria-selected={cat === c.id} onClick={() => setCat(c.id)}
                  className={cn("-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm", cat === c.id ? "border-brand text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
                  {c.label}<span className="rounded-full bg-foreground/10 px-1.5 text-xs tabular-nums">{counts[c.id] ?? 0}</span>
                </button>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">{CATEGORIES.find((c) => c.id === cat)!.hint}</p>
            {cat === "requirement" && <PrdExtract slug={slug} items={items} value={value} onChange={onChange} />}
            {editing && items.find((i) => i.key === editing) ? (
              <AddCard key={`edit-${editing}`} cat={cat} items={items} flowKeys={flowKeys} editKey={editing} initial={itemToValues(cat, items.find((i) => i.key === editing)!)}
                onCancel={() => setEditing(null)} onAdd={(md) => { onChange(replaceItem(value, editing, md)); setEditing(null); }} />
            ) : (
              <AddCard key={cat} cat={cat} items={items} flowKeys={flowKeys} onAdd={(md) => onChange(insertItem(value, CATEGORIES.find((c) => c.id === cat)!.heading, md))} />
            )}
            <div className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Already in this test plan</h3>
              {items.filter((i) => i.category === cat).map((i) => (
                <Card key={i.key} className="space-y-1 p-3 text-sm">
                  <div className="flex items-center gap-2"><Badge tone="accent">{i.key}</Badge><span className="font-medium">{i.title}</span>
                    <button className="ml-auto text-muted-foreground hover:text-foreground" aria-label={`Edit ${i.key}`} onClick={() => { setCat(cat); setEditing(i.key); }}><Pencil className="size-4" /></button>
                    <button className="text-muted-foreground hover:text-bad" aria-label={`Remove ${i.key}`} onClick={() => onChange(removeItem(value, i.key))}><Trash2 className="size-4" /></button></div>
                  <Summary item={i} />
                </Card>
              ))}
              {!counts[cat] && <div className="text-sm text-muted-foreground">Nothing here yet. Use the form above to add the first one.</div>}
            </div>
          </div>
          <aside className="space-y-3">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Is every requirement tested?</h3>
            <Card className="space-y-2 p-3 text-sm">
              {uncovered.length === 0 ? <div className="flex items-center gap-2 text-ok"><CheckCircle2 className="size-4" />Yes, every requirement is tested</div> : (
                <><div className="text-warn">{uncovered.length} requirement{uncovered.length > 1 ? "s" : ""} no journey tests yet:</div>
                  <div className="flex flex-wrap gap-1">{uncovered.map((r) => <Badge key={r} tone="warn">{r}</Badge>)}</div></>
              )}
            </Card>
          </aside>
        </div>
      )}

      {normalize !== null && <DiffDialog before={value} after={normalize} onAccept={() => { onChange(normalize); setNormalize(null); }} onClose={() => setNormalize(null)} />}
    </div>
  );
}

const Msg = ({ level, text }: { level: "error" | "warning"; text: string }) => (
  <div className="flex items-start gap-2 px-4 py-2 text-sm">
    {level === "error" ? <AlertCircle className="mt-0.5 size-4 shrink-0 text-bad" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />}<span>{text}</span>
  </div>
);

function Summary({ item }: { item: { category: string; body: Record<string, any> } }) {
  const b = item.body;
  const bits: [string, string][] = [];
  const add = (k: string, val: unknown) => { if (val && (!Array.isArray(val) || val.length)) bits.push([k, Array.isArray(val) ? val.join(", ") : typeof val === "object" ? Object.entries(val as object).map(([a, c]) => `${a}=${c}`).join(", ") : String(val)]); };
  for (const k of ["prd_ref", "acceptance", "priority", "severity", "covers", "checks", "verifies", "rule", "check", "targets", "pattern", "max_ms", "question", "note", "wait_for", "ignore_console", "applies_to", "expect", "test_data", "scope", "context"]) add(k, b[k]);
  if (item.category === "flow") { add("steps", `${b.steps?.length ?? 0}`); add("expectations", `${b.expect?.length ?? 0}`); }
  if (item.category === "reasoning_example") add("strategy", `${b.strategy?.length ?? 0} steps`);
  return <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-0.5 text-xs">{bits.map(([k, val]) => <><dt key={k} className="text-muted-foreground">{k}</dt><dd key={k + "v"} className="break-words font-mono">{val}</dd></>)}</dl>;
}

function AddCard({ cat, items, flowKeys, onAdd, initial, editKey, onCancel }: { cat: Category; items: { key: string }[]; flowKeys: string[]; onAdd: (md: string) => void; initial?: Record<string, string>; editKey?: string; onCancel?: () => void }) {
  const spec: FieldSpec[] = FORMS[cat].map((f) => (f.name === "applies_to" ? { ...f, options: flowKeys } : f));
  const init = () => Object.fromEntries(spec.map((f) => [f.name, f.kind === "select" ? (f.options?.[f.name === "severity" || f.name === "priority" ? 2 : 0] ?? "") : ""]));
  const [v, setV] = useState<Record<string, string>>(() => ({ ...init(), ...(initial ?? {}) }));
  const prefix = CATEGORIES.find((c) => c.id === cat)!.prefix;
  const missing = spec.filter((f) => f.required && (!f.show || f.show(v)) && !v[f.name]?.trim());
  const set = (name: string, val: string) => setV((p) => ({ ...p, [name]: val }));
  return (
    <Card className="space-y-3 p-4">
      <div className="font-medium">{editKey ? `Edit ${editKey}` : `Add ${CATEGORIES.find((c) => c.id === cat)!.label.toLowerCase().replace(/s$/, "")}`}</div>
      <div className="grid gap-3 md:grid-cols-2">
        {spec.filter((f) => !f.show || f.show(v)).map((f) => (
          <div key={f.name} className={cn(["area", "lines", "scope"].includes(f.kind) && "md:col-span-2")}>
            <Field label={f.label + (f.required ? " *" : "")} hint={f.hint}>
              {f.kind === "text" && <input className={inputCls} value={v[f.name]} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />}
              {(f.kind === "area" || f.kind === "lines") && <textarea className={cn(inputCls, "min-h-20", f.kind === "lines" && "font-mono text-xs")} value={v[f.name]} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />}
              {f.kind === "select" && <select className={inputCls} value={v[f.name]} onChange={(e) => set(f.name, e.target.value)}>{(f.options ?? []).map((o) => <option key={o}>{o}</option>)}</select>}
              {f.kind === "scope" && (
                <div className="flex flex-wrap gap-3 pt-1">
                  {f.options!.map((o) => {
                    const on = (v[f.name] ?? "").split(",").map((s) => s.trim()).includes(o);
                    return <label key={o} className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={on} onChange={() => set(f.name, (on ? (v[f.name] ?? "").split(",").map((s) => s.trim()).filter((s) => s && s !== o) : [...(v[f.name] ? v[f.name].split(",").map((s) => s.trim()) : []), o]).join(", "))} />{o}</label>;
                  })}
                </div>
              )}
            </Field>
          </div>
        ))}
      </div>
      <div className="flex justify-end gap-2">
        {editKey && <Button onClick={onCancel}>Cancel</Button>}
        <Button variant="primary" disabled={missing.length > 0} title={missing.length ? `Needs: ${missing.map((m) => m.label).join(", ")}` : undefined}
          onClick={() => { onAdd(itemMarkdown(cat, editKey ?? nextKey(items.map((i) => i.key), prefix), v)); if (!editKey) setV(init()); }}>
          {editKey ? <CheckCircle2 className="size-4" /> : <Plus className="size-4" />}{editKey ? "Save changes" : "Add to test plan"}
        </Button>
      </div>
    </Card>
  );
}

function PrdExtract({ slug, items, value, onChange }: { slug: string; items: { key: string }[]; value: string; onChange: (md: string) => void }) {
  const extract = useExtractPrd(slug);
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const proposals = extract.data?.proposals ?? [];
  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-center gap-2">
        <div><div className="font-medium">Suggest from your product document</div><p className="text-xs text-muted-foreground">AI reads the document saved in Settings and proposes requirements, each with a quote from it. You accept the ones you want.</p></div>
        <Button className="ml-auto" onClick={() => { setAccepted(new Set()); extract.mutate(); }} disabled={extract.isPending}><Sparkles className="size-4" />{extract.isPending ? "Reading…" : "Suggest requirements"}</Button>
      </div>
      {extract.error && <p role="alert" className="text-sm text-bad">{extract.error.message}</p>}
      {proposals.map((p) => (
        <div key={p.key} className="flex items-start gap-3 rounded-lg border border-border p-3 text-sm">
          <div className="min-w-0 flex-1 space-y-1">
            <div className="font-medium">{p.title} <span className="text-xs text-muted-foreground">({p.prd_ref}, {p.priority})</span></div>
            <div className="text-muted-foreground">{p.acceptance}</div>
            <div className="border-l-2 border-border pl-2 text-xs italic text-muted-foreground">“{p.quote}”</div>
          </div>
          <Button disabled={accepted.has(p.key)} onClick={() => {
            const key = nextKey([...items.map((i) => i.key), ...[...accepted].map((k) => k)], "REQ-");
            onChange(insertItem(value, "Requirements", itemMarkdown("requirement", key, { title: p.title, prd_ref: p.prd_ref, acceptance: p.acceptance, priority: p.priority })));
            setAccepted((s) => new Set(s).add(p.key));
          }}>{accepted.has(p.key) ? "Added" : "Accept"}</Button>
        </div>
      ))}
      {extract.isSuccess && !proposals.length && <p className="text-sm text-muted-foreground">No requirements in the PRD that its own text supports.</p>}
    </Card>
  );
}

function DiffDialog({ before, after, onAccept, onClose }: { before: string; after: string; onAccept: () => void; onClose: () => void }) {
  const d = useMemo(() => diffLines(before, after), [before, after]);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-3 sm:max-w-4xl" aria-label="Normalized playbook">
        <DialogHeader>
          <DialogTitle>Review the rewritten test plan</DialogTitle>
          <DialogDescription>Claude rewrote your text into the playbook format. Green lines are added, red lines are removed. Nothing changes until you accept.</DialogDescription>
        </DialogHeader>
        <pre className="flex-1 overflow-auto rounded-lg border bg-code p-2 font-mono text-xs leading-5">
          {d.map((l, i) => <div key={i} className={cn("whitespace-pre-wrap break-all px-2", l.type === "add" && "bg-ok-soft text-ok", l.type === "del" && "bg-bad-soft text-bad line-through")}>{l.type === "add" ? "+ " : l.type === "del" ? "- " : "  "}{l.text}</div>)}
        </pre>
        <DialogFooter><Button onClick={onClose}>Keep mine</Button><Button variant="primary" onClick={onAccept}>Use the rewritten version</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
