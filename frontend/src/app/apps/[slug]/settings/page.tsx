"use client";
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
        <Field label="Base URL"><input className={inputCls} value={f.base_url} onChange={set("base_url")} /></Field>
        <Field label="Description"><textarea className={inputCls} rows={2} value={f.description} onChange={set("description")} /></Field>
        <Field label="Product requirements (PRD)" hint="Markdown. The playbook editor can propose requirements from it."><textarea className={`${inputCls} font-mono text-xs`} rows={6} value={f.prd} onChange={set("prd")} /></Field>
        <Field label="Allowed hosts" hint="Comma-separated. The browser refuses navigation anywhere else."><input className={inputCls} value={f.hosts} onChange={set("hosts")} /></Field>
        <Field label="Default mode">
          <select className={inputCls} value={f.default_mode} onChange={(e) => setF({ ...f, default_mode: e.target.value as Mode })}>
            <option value="hybrid">Hybrid (Jev + Claude)</option><option value="baseline">Baseline (Claude only)</option><option value="stub">Stub</option>
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Auto-act min confidence" hint="Blank = global default (0.75)"><input className={inputCls} value={f.auto} onChange={set("auto")} inputMode="decimal" placeholder="0.75" /></Field>
          <Field label="Escalate min confidence" hint="Blank = global default (0.45)"><input className={inputCls} value={f.esc} onChange={set("esc")} inputMode="decimal" placeholder="0.45" /></Field>
        </div>
        {invalid && <p className="text-xs text-bad">Thresholds must be between 0 and 1, and escalate must be below auto.</p>}
        <Field label="Redacted keys" hint="JSON keys masked in stored request and response bodies. Authorization and cookie headers are never stored."><input className={inputCls} value={f.redact} onChange={set("redact")} /></Field>
        {save.error && <p role="alert" className="text-sm text-bad">{save.error.message}</p>}
        <div className="flex items-center justify-end gap-3">
          {save.isSuccess && <span className="text-sm text-ok">Saved</span>}
          <Button type="submit" variant="primary" disabled={invalid || save.isPending}>{save.isPending ? "Saving…" : "Save settings"}</Button>
        </div>
      </form>
    </Card>
  );
}
