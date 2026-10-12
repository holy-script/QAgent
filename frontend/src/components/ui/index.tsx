"use client";
/**
 * QAgent's shared building blocks. Buttons, badges, tabs and tooltips are shadcn/ui (Base UI) components;
 * this file adds the app-specific pieces (status pills, metrics, empty/error states) in one place so pages stay small.
 */
import { AlertTriangle, CircleHelp, Inbox, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentProps, ComponentType, ReactNode } from "react";
import { Badge as ShadBadge } from "@/components/ui/badge";
import { Button as ShadButton, buttonVariants } from "@/components/ui/button";
import { Tabs as ShadTabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export { cn };

type BtnProps = Omit<ComponentProps<typeof ShadButton>, "variant"> & { variant?: "primary" | "ghost" | "danger" };
const VARIANT = { primary: "default", ghost: "outline", danger: "destructive" } as const;
export function Button({ variant = "ghost", className, ...p }: BtnProps) {
  return <ShadButton variant={VARIANT[variant]} className={cn("h-9 px-3.5", className)} {...p} />;
}
export const LinkButton = ({ variant = "ghost", className, ...p }: ComponentProps<typeof Link> & { variant?: BtnProps["variant"] }) => (
  <Link {...p} className={cn(buttonVariants({ variant: VARIANT[variant] }), "h-9 px-3.5", className)} />
);

export const Card = ({ className, ...p }: ComponentProps<"div">) => (
  <div {...p} className={cn("rounded-xl border bg-card text-card-foreground shadow-(--shadow-card)", className)} />
);

const TONES = {
  neutral: "bg-muted text-muted-foreground border-border",
  ok: "bg-ok-soft text-ok border-ok/25",
  warn: "bg-warn-soft text-warn border-warn/30",
  bad: "bg-bad-soft text-bad border-bad/25",
  accent: "bg-brand-soft text-brand border-brand/25",
  violet: "bg-violet-soft text-violet border-violet/25",
} as const;
export type Tone = keyof typeof TONES;
export const Badge = ({ tone = "neutral", className, ...p }: Omit<ComponentProps<typeof ShadBadge>, "variant"> & { tone?: Tone }) => (
  <ShadBadge variant="outline" className={cn("h-auto rounded-md px-2 py-0.5", TONES[tone], className)} {...p} />
);

const STATUS: Record<string, [Tone, string]> = {
  queued: ["neutral", "Queued"], running: ["accent", "Running"], pending: ["neutral", "Waiting"],
  passed: ["ok", "Passed"], ok: ["ok", "OK"], failed: ["bad", "Failed"], error: ["bad", "Error"], stopped: ["warn", "Stopped"],
  draft: ["warn", "Draft"], confirmed: ["ok", "Ready to run"],
};
export function StatusPill({ status }: { status: string }) {
  const [tone, label] = STATUS[status] ?? ["neutral", status];
  return (
    <Badge tone={tone}>
      {status === "running" && <span className="size-1.5 rounded-full bg-brand pulse-ring" />}
      {label}
    </Badge>
  );
}

export const SEVERITY_TONE: Record<string, Tone> = { low: "neutral", medium: "warn", high: "bad", critical: "bad" };
export const SeverityBadge = ({ severity }: { severity: string }) => <Badge tone={SEVERITY_TONE[severity]}>{severity}</Badge>;

/** A small "?" that explains a term on hover or focus. Use it next to jargon. */
export function InfoTip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<button type="button" aria-label="What is this?" className={cn("inline-flex align-middle text-muted-foreground hover:text-foreground", className)} />}>
        <CircleHelp className="size-3.5" />
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-balance">{children}</TooltipContent>
    </Tooltip>
  );
}

const EDGE: Record<string, string> = { bad: "border-l-bad", ok: "border-l-ok", accent: "border-l-brand", warn: "border-l-warn", violet: "border-l-violet" };
const CHIP: Record<string, string> = { bad: "bg-bad-soft text-bad", ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", violet: "bg-violet-soft text-violet" };
export function Metric({ label, value, hint, tone, info, icon: Icon, extra }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone; info?: ReactNode; icon?: ComponentType<{ className?: string }>; extra?: ReactNode }) {
  return (
    <Card className={cn("relative overflow-hidden border-l-[3px] bg-gradient-to-br from-card to-secondary/60 px-4 py-3", EDGE[tone ?? "accent"] ?? "border-l-brand/60")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">{label}{info && <InfoTip>{info}</InfoTip>}</div>
          <div className={cn("mt-1 text-2xl font-semibold tabular-nums", tone === "bad" && "text-bad", tone === "ok" && "text-ok", tone === "accent" && "text-brand")}>{value}</div>
          {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
        </div>
        {Icon && <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg bg-chip text-brand", tone && CHIP[tone])}><Icon className="size-[18px]" /></span>}
      </div>
      {extra}
    </Card>
  );
}

export const Spinner = ({ className }: { className?: string }) => <Loader2 className={cn("size-4 animate-spin text-muted-foreground", className)} aria-label="Loading" />;
export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Spinner />{label}</div>
);

export function Empty({ title, hint, action, icon }: { title: string; hint?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed bg-card/50 px-4 py-14 text-center">
      <div className="text-muted-foreground">{icon ?? <Inbox className="size-8" />}</div>
      <div className="font-medium">{title}</div>
      {hint && <div className="max-w-sm text-sm text-muted-foreground">{hint}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 rounded-xl border border-bad/30 bg-bad-soft py-12 text-center">
      <AlertTriangle className="size-7 text-bad" />
      <div className="font-medium">Something went wrong</div>
      <div className="max-w-md text-sm text-muted-foreground">{error instanceof Error ? error.message : String(error)}</div>
      {retry && <Button onClick={retry} className="mt-2">Try again</Button>}
    </div>
  );
}

/** Link-based section tabs (one URL per tab). */
export type NavItem = { href: string; label: string; count?: number; exact?: boolean; icon?: ComponentType<{ className?: string }>; tour?: string };

export function Tabs({ tabs, className }: { tabs: NavItem[]; className?: string }) {
  const path = usePathname();
  return (
    <nav className={cn("flex gap-1 overflow-x-auto border-b", className)} aria-label="Sections">
      {tabs.map((t) => {
        const on = t.exact ? path === t.href : path === t.href || path.startsWith(t.href + "/");
        return (
          <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined} data-tour={t.tour}
            className={cn("-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm transition-colors",
              on ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {t.label}
            {t.count != null && t.count > 0 && <span className="rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">{t.count}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

/** The same sections as a vertical list, for wide screens (more room for the page itself). */
export function SideNav({ items, className }: { items: NavItem[]; className?: string }) {
  const path = usePathname();
  return (
    <nav className={cn("flex flex-col gap-0.5", className)} aria-label="Sections">
      {items.map((t) => {
        const on = t.exact ? path === t.href : path === t.href || path.startsWith(t.href + "/");
        const Icon = t.icon;
        return (
          <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined} data-tour={t.tour}
            className={cn("relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors", on ? "bg-card font-medium text-foreground shadow-sm before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-primary" : "text-muted-foreground hover:bg-card/70 hover:text-foreground")}>
            {Icon && <Icon className={cn("size-4 shrink-0", on && "text-brand")} />}
            <span className="flex-1">{t.label}</span>
            {t.count != null && t.count > 0 && <span className="rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">{t.count}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

/** State-driven tabs (the run page keeps its tab in component state). */
export function StateTabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void }) {
  return (
    <ShadTabs value={value} onValueChange={(v) => onChange(v as T)}>
      <TabsList variant="line" className="h-auto w-full justify-start overflow-x-auto border-b px-0">
        {tabs.map((t) => (
          <TabsTrigger key={t.id} value={t.id} className="flex-none gap-2 px-3.5 py-2.5">
            {t.label}
            {t.count != null && t.count > 0 && <span className="rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">{t.count}</span>}
          </TabsTrigger>
        ))}
      </TabsList>
    </ShadTabs>
  );
}

export const Field = ({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) => (
  <label className="block space-y-1.5">
    <span className="text-sm font-medium">{label}</span>
    {children}
    {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
  </label>
);
export const inputCls = "w-full rounded-lg border border-input bg-card px-3 py-2 text-sm shadow-xs outline-none transition placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30";

export { ago, fmtBytes, fmtMs, fmtUsd } from "./format";

export { TableCell, TableRow };

/** A bordered table with a header row. Rows are plain <TableRow>/<TableCell> children. */
export function SimpleTable({ head, children, className }: { head: string[]; children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-hidden rounded-xl border bg-card", className)}>
      <Table>
        <TableHeader className="bg-secondary">
          <TableRow className="hover:bg-transparent">{head.map((h) => <TableHead key={h} className="h-10 px-4 text-xs font-medium text-muted-foreground">{h}</TableHead>)}</TableRow>
        </TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </div>
  );
}

/** A dropdown built on the library's Select (use instead of a native <select>). */
export function SelectField({ value, onChange, options, label, className }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string; className?: string }) {
  return (
    <Select value={value} onValueChange={(v) => v != null && onChange(String(v))} items={options}>
      <SelectTrigger aria-label={label} className={cn("h-9 w-full bg-card", className)}><SelectValue /></SelectTrigger>
      <SelectContent>{options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
    </Select>
  );
}
