"use client";
import { Activity, Eye, EyeOff } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Card, Field, inputCls } from "@/components/ui";
import { auth } from "@/lib/api/auth";

export function LoginForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const next = useSearchParams().get("next");
  const [f, setF] = useState({ email: "", password: "" });
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <div className="mx-auto mt-12 max-w-sm space-y-6">
      <div className="space-y-2 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground"><Activity className="size-6" /></span>
        <h1 className="text-2xl font-semibold tracking-tight">Sign in to QAgent</h1>
        <p className="text-sm text-muted-foreground">Use the team account. Ask a teammate if you do not have it yet.</p>
      </div>
      <Card className="p-6">
        <form className="space-y-4" onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          try {
            await auth.login(f.email, f.password);
            await qc.invalidateQueries({ queryKey: ["me"] });
            router.replace(next && next.startsWith("/") ? next : "/");
          } catch (err) {
            setError(err instanceof Error ? err.message : "Could not sign in");
          } finally { setBusy(false); }
        }}>
          <Field label="Email"><input className={inputCls} type="email" autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required autoFocus /></Field>
          <Field label="Password">
            <div className="relative">
              <input className={`${inputCls} pr-10`} type={show ? "text" : "password"} autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required />
              <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground">
                {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </Field>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <Button type="submit" variant="primary" className="w-full" disabled={busy || !f.email || !f.password}>{busy ? "Signing in…" : "Sign in"}</Button>
        </form>
      </Card>
    </div>
  );
}
