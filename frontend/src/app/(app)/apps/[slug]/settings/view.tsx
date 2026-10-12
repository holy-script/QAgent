"use client";
import { SelectField } from "@/components/ui";
import { ConfirmDelete } from "@/components/confirm-delete";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { Badge, Button, Card, ErrorState, Field, Loading, SimpleTable, fmtBytes, inputCls } from "@/components/ui";
import { TableCell, TableRow } from "@/components/ui/table";
import { Upload } from "lucide-react";
import { MAX_FILE_BYTES, api } from "@/lib/api/client";
import { useApp } from "@/lib/api/hooks";
import type { App, Mode } from "@/lib/api/types";

export default function Settings() {
  const { slug } = useParams<{ slug: string }>();
  const { data: app, error, isPending, refetch } = useApp(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return <div className="mx-auto max-w-2xl space-y-6"><Form key={app.id} app={app} /><TestFiles key={`f${app.id}`} app={app} /><Retention key={`r${app.id}`} app={app} /></div>;
}

const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

function Form({ app }: { app: App }) {
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: (p: Partial<App>) => api.updateApp(app.slug, p),
    onSuccess: (a) => qc.setQueryData(["app", app.slug], a),
  });
  const [f, setF] = useState({
    name: app.name, base_url: app.base_url, description: app.description, default_mode: app.default_mode,
    prd: app.prd_markdown ?? "", hosts: app.allowed_hosts.join(", "), redact: app.redact_keys.join(", "),
    auto: app.gate_overrides.auto_min?.toString() ?? "", esc: app.gate_overrides.escalate_min?.toString() ?? "",
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const num = (s: string) => (s === "" ? undefined : Number(s));
  const bad = (s: string) => s !== "" && !(Number(s) >= 0 && Number(s) <= 1);
  const invalid = !f.name.trim() || bad(f.auto) || bad(f.esc) || (f.auto !== "" && f.esc !== "" && Number(f.esc) >= Number(f.auto));

  return (
    <Card className="p-6">
      <form className="space-y-5" onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ name: f.name.trim(), base_url: f.base_url, description: f.description, prd_markdown: f.prd, default_mode: f.default_mode, allowed_hosts: list(f.hosts), redact_keys: list(f.redact), gate_overrides: { auto_min: num(f.auto), escalate_min: num(f.esc) } });
      }}>
        <Field label="Name"><input className={inputCls} value={f.name} onChange={set("name")} /></Field>
        <Field label="Website address" hint="Where test runs start."><input className={inputCls} value={f.base_url} onChange={set("base_url")} /></Field>
        <Field label="Description"><textarea className={inputCls} rows={2} value={f.description} onChange={set("description")} /></Field>
        <Field label="Product document (optional)" hint="Paste your requirements or product spec. The test plan editor can suggest requirements from it."><textarea className={`${inputCls} font-mono text-xs`} rows={6} value={f.prd} onChange={set("prd")} /></Field>
        <Field label="Other sites tests may visit" hint="Comma-separated. For safety the browser refuses to go anywhere that is not your app or listed here."><input className={inputCls} value={f.hosts} onChange={set("hosts")} /></Field>
        <Field label="Default mode" hint="How decisions are made when you run a test. Smart is recommended.">
          <SelectField label="Default mode" value={f.default_mode} onChange={(v) => setF({ ...f, default_mode: v as Mode })}
            options={[{ value: "hybrid", label: "Smart: fast AI, stronger AI when unsure (recommended)" }, { value: "baseline", label: "Thorough: stronger AI every time" }, { value: "stub", label: "Practice: no AI" }]} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Act on its own above this confidence" hint="0 to 1. Blank uses the default (0.75)."><input className={inputCls} value={f.auto} onChange={set("auto")} inputMode="decimal" placeholder="0.75" /></Field>
          <Field label="Ask the stronger AI above this confidence" hint="0 to 1. Below it the step stops instead of guessing. Blank uses the default (0.45)."><input className={inputCls} value={f.esc} onChange={set("esc")} inputMode="decimal" placeholder="0.45" /></Field>
        </div>
        {invalid && <p className="text-xs text-bad">Both numbers must be between 0 and 1, and the second must be lower than the first.</p>}
        <Field label="Hide these values in saved server calls" hint="Names of fields (for example email, card) whose values are replaced with [redacted] in stored server calls. Passwords and cookies in headers are never stored."><input className={inputCls} value={f.redact} onChange={set("redact")} /></Field>
        {save.error && <p role="alert" className="text-sm text-bad">{save.error.message}</p>}
        <div className="flex items-center justify-end gap-3">
          {save.isSuccess && <span className="text-sm text-ok">Saved</span>}
          <Button type="submit" variant="primary" disabled={invalid || save.isPending}>{save.isPending ? "Saving…" : "Save settings"}</Button>
        </div>
      </form>
      <DangerZone app={app} />
    </Card>
  );
}

/** Deleting an app removes everything it owns; the user must type the app's name first. */
function DangerZone({ app }: { app: App }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const del = useMutation({
    mutationFn: () => api.deleteApp(app.slug),
    onSuccess: () => { qc.clear(); toast.success(`${app.name} was deleted`); router.replace("/"); },
  });
  return (
    <div className="mt-8 space-y-3 rounded-lg border border-bad/40 bg-bad-soft p-4">
      <div>
        <div className="font-medium text-bad">Delete this app</div>
        <p className="text-sm text-muted-foreground">Removes the app together with its test plans, every run, bugs, reports, screenshots and other stored files. This cannot be undone.</p>
      </div>
      <Button variant="danger" onClick={() => setOpen(true)}>Delete {app.name}…</Button>
      <ConfirmDelete open={open} onOpenChange={setOpen} title={`Delete ${app.name}?`} confirmText={app.name} actionLabel="Delete everything"
        pending={del.isPending} error={del.error?.message} onConfirm={() => del.mutate()}>
        <p>This permanently deletes <b>{app.name}</b> and all of its data.</p>
        <p className="text-muted-foreground">If a test run is in progress, stop it first.</p>
      </ConfirmDelete>
    </div>
  );
}

/** Each app decides how long its own finished runs are kept. Nothing is deleted until a number is set. */
function Retention({ app }: { app: App }) {
  const qc = useQueryClient();
  const [days, setDays] = useState(app.retention_days?.toString() ?? "");
  const [keep, setKeep] = useState(app.retention_keep_last.toString());
  const [confirm, setConfirm] = useState(false);
  const status = useQuery({ queryKey: ["retention", app.slug], queryFn: () => api.retention(app.slug) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["retention", app.slug] }); qc.invalidateQueries({ queryKey: ["runs", app.slug] }); qc.invalidateQueries({ queryKey: ["app", app.slug] }); };
  const save = useMutation({
    mutationFn: () => api.updateApp(app.slug, { retention_days: days === "" ? null : Number(days), retention_keep_last: Number(keep) }),
    onSuccess: (a) => { qc.setQueryData(["app", app.slug], a); refresh(); toast.success("Clean-up policy saved"); },
  });
  const clean = useMutation({
    mutationFn: () => api.cleanRetention(app.slug),
    onSuccess: (r) => { setConfirm(false); refresh(); toast.success(`Deleted ${r.runs_deleted} ${r.runs_deleted === 1 ? "run" : "runs"}`); },
  });
  const badDays = days !== "" && !(Number.isInteger(Number(days)) && Number(days) >= 1);
  const badKeep = !(Number.isInteger(Number(keep)) && Number(keep) >= 0);
  const st = status.data;
  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="font-medium">Keeping old runs</h2>
        <p className="text-sm text-muted-foreground">Old test runs take up space (screenshots, recordings, reports). This policy applies to {app.name} only and runs automatically every hour. Leave the days blank to keep everything.</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Delete runs older than (days)" hint="Blank keeps runs for ever."><input className={inputCls} value={days} onChange={(e) => setDays(e.target.value)} inputMode="numeric" placeholder="Keep for ever" aria-label="Delete runs older than (days)" /></Field>
        <Field label="Always keep the newest" hint="Number of runs, whatever their age."><input className={inputCls} value={keep} onChange={(e) => setKeep(e.target.value)} inputMode="numeric" aria-label="Always keep the newest runs" /></Field>
      </div>
      {(badDays || badKeep) && <p className="text-xs text-bad">Days must be a whole number of 1 or more, and the number of runs to keep 0 or more.</p>}
      {save.error && <p role="alert" className="text-sm text-bad">{save.error.message}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {!st ? "Checking…" : !st.retention_days ? `${st.total_runs} runs stored; none will be deleted.` : `${st.would_delete} of ${st.total_runs} runs would be deleted right now.`}
        </p>
        <div className="flex gap-2">
          <Button variant="danger" disabled={!st || !st.would_delete} onClick={() => setConfirm(true)}>Clean up now…</Button>
          <Button variant="primary" disabled={badDays || badKeep || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save policy"}</Button>
        </div>
      </div>
      <ConfirmDelete open={confirm} onOpenChange={setConfirm} title={`Delete ${st?.would_delete ?? 0} old runs?`} actionLabel="Delete old runs" pending={clean.isPending} error={clean.error?.message} onConfirm={() => clean.mutate()}>
        <p>Runs older than {st?.retention_days} days (except the newest {st?.retention_keep_last}) are removed with their screenshots, proof and reports. Bugs that only those runs found disappear too.</p>
        <p className="text-muted-foreground">Save the policy first if you changed the numbers above.</p>
      </ConfirmDelete>
    </Card>
  );
}

/** Files a test can upload when a page has a file field (an avatar, a CSV import, an invoice). */
function TestFiles({ app }: { app: App }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const files = useQuery({ queryKey: ["files", app.slug], queryFn: () => api.listFiles(app.slug) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["files", app.slug] });
  const add = useMutation({
    mutationFn: async (list: File[]) => { for (const f of list) await api.uploadFile(app.slug, f); return list.length; },
    onSuccess: (n) => { refresh(); toast.success(n === 1 ? "File added" : `${n} files added`); },
  });
  const remove = useMutation({ mutationFn: (id: string) => api.deleteFile(app.slug, id), onSuccess: () => { refresh(); toast.success("File removed"); } });
  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="font-medium">Test files</h2>
        <p className="text-sm text-muted-foreground">When a page asks for a file (a profile photo, a spreadsheet to import), QAgent attaches one of these. Say which in the test plan with <code className="rounded bg-muted px-1">file: report.pdf</code> under Test data, or by naming it in the step. Without either, it picks a file that matches what the field accepts. Files up to {MAX_FILE_BYTES / (1024 * 1024)} MB.</p>
      </div>
      {files.isPending ? <p className="text-sm text-muted-foreground">Loading files…</p> : files.error ? <ErrorState error={files.error} retry={files.refetch} /> : (
        <SimpleTable head={["Name", "Type", "Size", ""]}>
          {files.data.map((f) => (
            <TableRow key={f.id}>
              <TableCell className="px-4 font-medium">{f.name} {f.builtin && <Badge tone="neutral">built in</Badge>}</TableCell>
              <TableCell className="px-4 text-muted-foreground">{f.content_type}</TableCell>
              <TableCell className="px-4 tabular-nums text-muted-foreground">{fmtBytes(f.size_bytes)}</TableCell>
              <TableCell className="px-4 text-right">{!f.builtin && <Button variant="danger" onClick={() => remove.mutate(f.id)} aria-label={`Remove ${f.name}`}>Remove</Button>}</TableCell>
            </TableRow>
          ))}
        </SimpleTable>
      )}
      {(add.error || remove.error) && <p role="alert" className="text-sm text-bad">{(add.error ?? remove.error)!.message}</p>}
      <input ref={input} type="file" multiple hidden aria-label="Choose test files" onChange={(e) => { const list = Array.from(e.target.files ?? []); e.target.value = ""; if (list.length) add.mutate(list); }} />
      <Button onClick={() => input.current?.click()} disabled={add.isPending}><Upload className="size-4" />{add.isPending ? "Adding…" : "Add files"}</Button>
    </Card>
  );
}
