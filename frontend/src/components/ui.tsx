"use client";
import clsx, { type ClassValue } from "clsx";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { twMerge } from "tailwind-merge";
import type { ComponentProps, ReactNode } from "react";

export const cn = (...c: ClassValue[]) => twMerge(clsx(c));

type BtnProps = ComponentProps<"button"> & { variant?: "primary" | "ghost" | "danger" };
export function Button({ variant = "ghost", className, ...p }: BtnProps) {
  return (
    <button
      {...p}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-accent text-slate-950 hover:brightness-110",
        variant === "ghost" && "border border-line bg-white/[0.03] hover:bg-white/[0.08]",
        variant === "danger" && "border border-bad/40 text-bad hover:bg-bad/10",
        className,
      )}
    />
  );
}
export const LinkButton = ({ variant = "ghost", className, ...p }: ComponentProps<typeof Link> & { variant?: BtnProps["variant"] }) => (
  <Link {...p} className={cn("inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition",
    variant === "primary" ? "bg-accent text-slate-950 hover:brightness-110" : "border border-line bg-white/[0.03] hover:bg-white/[0.08]", className)} />
);

export const Card = ({ className, ...p }: ComponentProps<"div">) => (
  <div {...p} className={cn("rounded-xl border border-line bg-surface/80 backdrop-blur", className)} />
);

const TONES = {
  neutral: "bg-white/[0.06] text-slate-300 border-line",
  ok: "bg-ok/10 text-ok border-ok/30",
  warn: "bg-warn/10 text-warn border-warn/30",
  bad: "bg-bad/10 text-bad border-bad/30",
  accent: "bg-accent/10 text-accent border-accent/30",
  violet: "bg-violet/10 text-violet border-violet/30",
} as const;
export type Tone = keyof typeof TONES;
export const Badge = ({ tone = "neutral", className, ...p }: ComponentProps<"span"> & { tone?: Tone }) => (
  <span {...p} className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium", TONES[tone], className)} />
);

const STATUS: Record<string, [Tone, string]> = {
  queued: ["neutral", "Queued"], running: ["accent", "Running"], pending: ["neutral", "Pending"],
  passed: ["ok", "Passed"], ok: ["ok", "OK"], failed: ["bad", "Failed"], error: ["bad", "Error"], stopped: ["warn", "Stopped"],
  draft: ["warn", "Draft"], confirmed: ["ok", "Confirmed"],
};
export function StatusPill({ status }: { status: string }) {
  const [tone, label] = STATUS[status] ?? ["neutral", status];
  return (
    <Badge tone={tone}>
      {status === "running" && <span className="size-1.5 rounded-full bg-accent pulse-ring" />}
      {label}
    </Badge>
  );
}

export const SEVERITY_TONE: Record<string, Tone> = { low: "neutral", medium: "warn", high: "bad", critical: "bad" };
export const SeverityBadge = ({ severity }: { severity: string }) => <Badge tone={SEVERITY_TONE[severity]}>{severity}</Badge>;

export function Metric({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <Card className="px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold tabular-nums", tone === "bad" && "text-bad", tone === "ok" && "text-ok", tone === "accent" && "text-accent")}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </Card>
  );
}

export const Spinner = ({ className }: { className?: string }) => <Loader2 className={cn("size-4 animate-spin text-muted", className)} aria-label="Loading" />;
export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted"><Spinner />{label}</div>
);

export function Empty({ title, hint, action, icon }: { title: string; hint?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line py-14 text-center">
      <div className="text-muted">{icon ?? <Inbox className="size-8" />}</div>
      <div className="font-medium">{title}</div>
      {hint && <div className="max-w-sm text-sm text-muted">{hint}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 rounded-xl border border-bad/30 bg-bad/5 py-12 text-center">
      <AlertTriangle className="size-7 text-bad" />
      <div className="font-medium">Something went wrong</div>
      <div className="max-w-md text-sm text-muted">{error instanceof Error ? error.message : String(error)}</div>
      {retry && <Button onClick={retry} className="mt-2">Try again</Button>}
    </div>
  );
}

export function Tabs({ tabs }: { tabs: { href: string; label: string; count?: number; exact?: boolean }[] }) {
  const path = usePathname();
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-line" aria-label="Sections">
      {tabs.map((t) => {
        const on = t.exact ? path === t.href : path === t.href || path.startsWith(t.href + "/");
        return (
          <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined}
            className={cn("-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm transition",
              on ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground")}>
            {t.label}
            {t.count != null && t.count > 0 && <span className="rounded-full bg-white/10 px-1.5 text-xs tabular-nums">{t.count}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

/** Same look as Tabs but state-driven (run page tabs live in one client component). */
export function StateTabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cn("-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm transition",
            value === t.id ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground")}>
          {t.label}
          {t.count != null && t.count > 0 && <span className="rounded-full bg-white/10 px-1.5 text-xs tabular-nums">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export const Field = ({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) => (
  <label className="block space-y-1.5">
    <span className="text-sm font-medium">{label}</span>
    {children}
    {hint && <span className="block text-xs text-muted">{hint}</span>}
  </label>
);
export const inputCls = "w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm placeholder:text-muted/60 focus:border-accent focus:outline-none";

export const fmtMs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`);
export const fmtBytes = (b: number) => (b < 1024 ? `${b} B` : `${(b / 1024).toFixed(1)} KB`);
export const fmtUsd = (n: number) => `$${n < 0.01 ? n.toFixed(4) : n.toFixed(2)}`;
export const ago = (iso: string) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m ago` : s < 86400 ? `${Math.floor(s / 3600)}h ago` : `${Math.floor(s / 86400)}d ago`;
};
