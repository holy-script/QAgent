"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DictatableInput, DictatableTextarea } from "@/components/dictation";
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
      <div><h1 className="text-2xl font-semibold tracking-tight">Add an app</h1><p className="mt-1 text-sm text-muted-foreground">Tell QAgent where your app lives. You can add test plans and run tests on the next screen.</p></div>
      <Card className="p-6">
        <form className="space-y-5" onSubmit={async (e) => {
          e.preventDefault();
          const app = await create.mutateAsync({ ...f, name: f.name.trim() });
          router.push(`/apps/${app.slug}/settings?guide=describe`); // the setup guide starts right away
        }}>
          <Field label="Name" hint="Any name you will recognise, e.g. “Online shop (staging)”."><DictatableInput value={f.name} onChange={(v) => setF((p) => ({ ...p, name: v }))} placeholder="Demo Shop" required autoFocus aria-label="Name" /></Field>
          <Field label="Website address" hint="Where QAgent starts. For safety, test runs can only visit this site (and any extra sites you allow in Settings).">
            <input className={inputCls} value={f.base_url} onChange={set("base_url")} inputMode="url" required />
            {f.base_url && urlError && <span className="block text-xs text-bad">{urlError}</span>}
          </Field>
          <Field label="What does it do? (optional)"><DictatableTextarea rows={3} value={f.description} onChange={(v) => setF((p) => ({ ...p, description: v }))} refine="description" tidyLabel="Tidy up with AI" placeholder="A short description for your teammates. You can dictate it." aria-label="What does it do?" /></Field>
          {create.error && <p role="alert" className="text-sm text-bad">{create.error.message}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" onClick={() => router.back()}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={!valid || create.isPending}>{create.isPending ? "Adding…" : "Add app"}</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
