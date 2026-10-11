"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Field, inputCls } from "@/components/ui";
import { useCreateApp } from "@/lib/api/hooks";

export default function NewApp() {
  const router = useRouter();
  const create = useCreateApp();
  const [f, setF] = useState({ name: "", base_url: "http://localhost:8001", description: "" });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  let urlError = "";
  try { const u = new URL(f.base_url); if (!/^https?:$/.test(u.protocol)) urlError = "Use http:// or https://"; } catch { urlError = "Enter a full URL, e.g. http://localhost:8001"; }
  const valid = f.name.trim() && !urlError;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">New app</h1>
      <Card className="p-6">
        <form className="space-y-5" onSubmit={async (e) => {
          e.preventDefault();
          const app = await create.mutateAsync({ ...f, name: f.name.trim() });
          router.push(`/apps/${app.slug}`);
        }}>
          <Field label="Name"><input className={inputCls} value={f.name} onChange={set("name")} placeholder="Demo Shop" required autoFocus /></Field>
          <Field label="Base URL" hint="Runs may only visit this host (plus any allowed hosts you add later).">
            <input className={inputCls} value={f.base_url} onChange={set("base_url")} inputMode="url" required />
            {f.base_url && urlError && <span className="block text-xs text-bad">{urlError}</span>}
          </Field>
          <Field label="Description"><textarea className={inputCls} rows={3} value={f.description} onChange={set("description")} placeholder="What does this app do?" /></Field>
          {create.error && <p role="alert" className="text-sm text-bad">{create.error.message}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" onClick={() => router.back()}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={!valid || create.isPending}>{create.isPending ? "Creating…" : "Create app"}</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
