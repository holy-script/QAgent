"use client";
import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/components/ui";

/**
 * Dependency-free charts that follow the theme tokens. Each has hover/keyboard values, labelled axes and a text
 * alternative (an off-screen table), and never relies on colour alone (legends say what each colour means).
 */

export interface Day { date: string; passed: number; failed: number; findings?: number; cost_usd?: number }

const shortDate = (iso: string) => new Date(iso + "T00:00:00Z").toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });

/** Shared frame: plot area, hover guide, floating tooltip, ←/→ keys, and a table for screen readers. */
function HoverFrame({ n, height, label, tooltip, table, children }: {
  n: number; height: string; label: string; tooltip: (i: number) => ReactNode; table: ReactNode; children: (hover: number | null) => ReactNode;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") { setHover((h) => Math.min(n - 1, (h ?? -1) + 1)); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { setHover((h) => Math.max(0, (h ?? n) - 1)); e.preventDefault(); }
    else if (e.key === "Escape") setHover(null);
  };
  const pct = hover == null ? 0 : ((hover + 0.5) / n) * 100;
  return (
    <div className={cn("relative", height)} tabIndex={0} role="group" aria-label={`${label}. Use the left and right arrow keys to read each day.`} onKeyDown={onKey} onBlur={() => setHover(null)} onMouseLeave={() => setHover(null)}>
      {children(hover)}
      <div className="absolute inset-0 flex" aria-hidden>
        {Array.from({ length: n }, (_, i) => <div key={i} className="h-full flex-1" onMouseEnter={() => setHover(i)} />)}
      </div>
      {hover != null && (
        <div className="pointer-events-none absolute top-0 z-10 w-max max-w-[11rem] -translate-x-1/2 rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg" style={{ left: `${Math.min(88, Math.max(12, pct))}%` }} role="status">
          {tooltip(hover)}
        </div>
      )}
      <table className="sr-only"><tbody>{table}</tbody></table>
    </div>
  );
}

const Legend = ({ items }: { items: { color: string; label: string }[] }) => (
  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
    {items.map((i) => <span key={i.label} className="flex items-center gap-1.5"><i className={cn("size-2.5 rounded-sm", i.color)} />{i.label}</span>)}
  </div>
);

const ticks = (max: number) => { const top = Math.max(1, Math.ceil(max)); return [top, Math.round(top / 2), 0]; };

/** Runs per day: green is clean, red had problems. */
export function RunsChart({ series, label }: { series: Day[]; label: string }) {
  const id = useId();
  const max = Math.max(1, ...series.map((d) => d.passed + d.failed));
  const [top, mid] = ticks(max);
  const W = 100, H = 100, gap = series.length > 45 ? 0.25 : 0.7, bw = W / series.length - gap;
  const y = (v: number) => H - (v / top) * H;
  return (
    <figure className="space-y-2">
      <div className="grid grid-cols-[1.5rem_1fr] gap-2">
        <div className="flex h-44 flex-col justify-between text-right text-[10px] tabular-nums text-muted-foreground" aria-hidden><span>{top}</span><span>{mid}</span><span>0</span></div>
        <div>
          <HoverFrame n={series.length} height="h-44" label={label}
            tooltip={(i) => <><div className="font-medium">{shortDate(series[i].date)}</div><div className="mt-1 flex items-center gap-1.5"><i className="size-2 rounded-full bg-ok" />{series[i].passed} without problems</div><div className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-bad" />{series[i].failed} with problems</div></>}
            table={series.map((d) => <tr key={d.date}><th>{d.date}</th><td>{d.passed} without problems</td><td>{d.failed} with problems</td></tr>)}>
            {(hover) => (
              <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="size-full" aria-hidden>
                <defs>
                  <linearGradient id={`${id}ok`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--ok)" stopOpacity="0.95" /><stop offset="1" stopColor="var(--ok)" stopOpacity="0.55" /></linearGradient>
                  <linearGradient id={`${id}bad`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--bad)" stopOpacity="0.95" /><stop offset="1" stopColor="var(--bad)" stopOpacity="0.6" /></linearGradient>
                </defs>
                {[0, 0.5, 1].map((f) => <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="var(--border)" strokeWidth="0.4" strokeDasharray={f === 1 ? undefined : "1.5 1.5"} vectorEffect="non-scaling-stroke" />)}
                {hover != null && <rect x={hover * (W / series.length)} y="0" width={W / series.length} height={H} fill="var(--brand)" opacity="0.08" />}
                {series.map((d, i) => {
                  const x = i * (W / series.length) + gap / 2, hp = H - y(d.passed), hf = H - y(d.failed);
                  return <g key={d.date} opacity={hover == null || hover === i ? 1 : 0.55}>
                    {hp > 0 && <rect x={x} y={y(d.passed)} width={bw} height={hp} fill={`url(#${id}ok)`} />}
                    {hf > 0 && <rect x={x} y={y(d.passed) - hf} width={bw} height={hf} rx="0.6" fill={`url(#${id}bad)`} />}
                  </g>;
                })}
              </svg>
            )}
          </HoverFrame>
          <div className="mt-1 flex justify-between text-[10px] text-muted-foreground" aria-hidden><span>{shortDate(series[0].date)}</span><span>{shortDate(series[Math.floor(series.length / 2)].date)}</span><span>{shortDate(series.at(-1)!.date)}</span></div>
        </div>
      </div>
      <Legend items={[{ color: "bg-ok", label: "No problems" }, { color: "bg-bad", label: "Problems found" }]} />
    </figure>
  );
}

/** A smooth filled line over time (used for AI cost per day). */
export function AreaTrend({ series, pick, format, label, color = "var(--brand)" }: {
  series: Day[]; pick: (d: Day) => number; format: (v: number) => string; label: string; color?: string;
}) {
  const id = useId();
  const vals = series.map(pick);
  const max = Math.max(1e-9, ...vals) * 1.15;
  const W = 100, H = 100;
  const pts = vals.map((v, i) => [((i + 0.5) / vals.length) * W, H - (v / max) * H] as const);
  const path = pts.map(([x, y], i) => {
    if (i === 0) return `M${x},${y}`;
    const [px, py] = pts[i - 1], cx = (px + x) / 2;
    return `C${cx},${py} ${cx},${y} ${x},${y}`;
  }).join(" ");
  const area = `${path} L${pts.at(-1)![0]},${H} L${pts[0][0]},${H} Z`;
  return (
    <figure className="space-y-2">
      <HoverFrame n={series.length} height="h-44" label={label}
        tooltip={(i) => <><div className="font-medium">{shortDate(series[i].date)}</div><div className="mt-1 tabular-nums">{format(vals[i])}</div></>}
        table={series.map((d, i) => <tr key={d.date}><th>{d.date}</th><td>{format(vals[i])}</td></tr>)}>
        {(hover) => (
          <>
            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="size-full" aria-hidden>
              <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity="0.45" /><stop offset="1" stopColor={color} stopOpacity="0.02" /></linearGradient></defs>
              {[0, 0.5, 1].map((f) => <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="var(--border)" strokeWidth="0.4" strokeDasharray={f === 1 ? undefined : "1.5 1.5"} vectorEffect="non-scaling-stroke" />)}
              <path d={area} fill={`url(#${id})`} />
              <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            </svg>
            {hover != null && <span className="pointer-events-none absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card" style={{ left: `${pts[hover][0]}%`, top: `${pts[hover][1]}%`, background: color }} />}
          </>
        )}
      </HoverFrame>
      <div className="flex justify-between text-[10px] text-muted-foreground" aria-hidden><span>{shortDate(series[0].date)}</span><span>{shortDate(series.at(-1)!.date)}</span></div>
    </figure>
  );
}

/** Tiny trend line for a stat card. */
export function Sparkline({ values, color = "var(--brand)", className }: { values: number[]; color?: string; className?: string }) {
  const id = useId();
  if (values.length < 2) return null;
  const max = Math.max(1e-9, ...values), min = Math.min(...values), span = Math.max(1e-9, max - min);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * 100, 28 - ((v - min) / span) * 24] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={cn("h-8 w-full", className)} aria-hidden>
      <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity="0.35" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <path d={`${line} L100,32 L0,32 Z`} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Half-circle gauge for a percentage. */
export function Gauge({ value, label, sub }: { value: number | null; label: string; sub?: string }) {
  const id = useId();
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value));
  const R = 70, C = Math.PI * R;
  const tone = value == null ? "var(--muted-foreground)" : pct >= 0.8 ? "var(--ok)" : pct >= 0.5 ? "var(--warn)" : "var(--bad)";
  return (
    <figure className="flex flex-col items-center" aria-label={label}>
      <svg viewBox="0 0 180 104" className="w-full max-w-[16rem]" role="img" aria-label={`${label}: ${value == null ? "no finished runs yet" : Math.round(pct * 100) + " percent"}`}>
        <defs><linearGradient id={id} x1="0" x2="1"><stop offset="0" stopColor={tone} stopOpacity="0.55" /><stop offset="1" stopColor={tone} /></linearGradient></defs>
        <path d="M20,90 A70,70 0 0 1 160,90" fill="none" stroke="var(--secondary)" strokeWidth="16" strokeLinecap="round" />
        <path d="M20,90 A70,70 0 0 1 160,90" fill="none" stroke={`url(#${id})`} strokeWidth="16" strokeLinecap="round" strokeDasharray={`${C * pct} ${C}`} />
        <text x="90" y="82" textAnchor="middle" className="fill-foreground text-[28px] font-semibold tabular-nums">{value == null ? "–" : `${Math.round(pct * 100)}%`}</text>
      </svg>
      <figcaption className="-mt-1 text-center text-xs text-muted-foreground">{sub}</figcaption>
    </figure>
  );
}

const BAR: Record<string, string> = { critical: "from-bad/70 to-bad", high: "from-warn/70 to-warn", medium: "from-violet/70 to-violet", low: "from-brand/60 to-brand", ok: "from-ok/70 to-ok", bad: "from-bad/70 to-bad", neutral: "from-muted-foreground/50 to-muted-foreground" };

/** Horizontal bars with a gradient fill and the number at the end. */
export function HBars({ rows }: { rows: { label: string; value: number; tone: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[5rem_1fr_1.75rem] items-center gap-3 text-sm">
          <span className="capitalize text-muted-foreground">{r.label}</span>
          <span className="h-3 overflow-hidden rounded-full bg-secondary"><span className={cn("block h-full rounded-full bg-gradient-to-r", BAR[r.tone] ?? BAR.low)} style={{ width: `${(r.value / max) * 100}%` }} /></span>
          <span className="text-right font-medium tabular-nums">{r.value}</span>
        </li>
      ))}
    </ul>
  );
}

/** One stacked bar split into labelled parts (for example open / came back / fixed). */
export function SplitBar({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const total = parts.reduce((n, p) => n + p.value, 0);
  return (
    <div className="space-y-2">
      <div className="flex h-3 overflow-hidden rounded-full bg-secondary" role="img" aria-label={parts.map((p) => `${p.value} ${p.label}`).join(", ")}>
        {total > 0 && parts.map((p) => p.value > 0 && <span key={p.label} className={p.color} style={{ width: `${(p.value / total) * 100}%` }} />)}
      </div>
      <Legend items={parts.map((p) => ({ color: p.color, label: `${p.value} ${p.label}` }))} />
    </div>
  );
}

const DOT: Record<string, string> = { passed: "bg-ok", failed: "bg-bad", error: "bg-bad", stopped: "bg-warn", running: "bg-brand", queued: "bg-muted-foreground", pending: "bg-muted-foreground" };

/** The last few runs of an app as coloured bars, oldest on the left. */
export function StatusStrip({ statuses }: { statuses: string[] }) {
  return (
    <span className="flex items-end gap-[3px]" role="img" aria-label={`Last ${statuses.length} runs: ${statuses.filter((s) => s === "passed").length} without problems`}>
      {[...statuses].reverse().map((s, i) => <i key={i} title={s} className={cn("w-1.5 rounded-sm", s === "passed" ? "h-5" : "h-3.5", DOT[s] ?? "bg-muted-foreground")} />)}
    </span>
  );
}
