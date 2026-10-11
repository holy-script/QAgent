"use client";
import { ConfirmDelete } from "@/components/confirm-delete";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorState, Field, Loading, inputCls } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useApp } from "@/lib/api/hooks";
import type { App, Mode } from "@/lib/api/types";

export default function Settings() {
  const { slug } = useParams<{ slug: string }>();
  const { data: app, error, isPending, refetch } = useApp(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return <Form key={app.id} app={app} />;
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
    <Card className="mx-auto max-w-2xl p-6">
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
          <select className={inputCls} value={f.default_mode} onChange={(e) => setF({ ...f, default_mode: e.target.value as Mode })}>
            <option value="hybrid">Smart: fast AI, stronger AI when unsure (recommended)</option><option value="baseline">Thorough: stronger AI every time</option><option value="stub">Practice: no AI</option>
          </select>
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
