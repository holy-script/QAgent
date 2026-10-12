import { cn } from "@/components/ui";

/** Small, dependency-free charts that follow the theme tokens. Each one carries a text summary for screen readers. */

export interface Day { date: string; passed: number; failed: number }

/** One stacked bar per day: finished without problems (green) and with problems (red). */
export function RunBars({ series, label }: { series: Day[]; label: string }) {
  const max = Math.max(1, ...series.map((d) => d.passed + d.failed));
  const W = 600, H = 150, pad = 18, gap = series.length > 45 ? 1 : 3;
  const bw = (W - pad) / series.length - gap;
  const first = series[0]?.date, last = series.at(-1)?.date;
  return (
    <figure className="space-y-1">
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="h-44 w-full" role="img" aria-label={label} preserveAspectRatio="none">
        {[0.5, 1].map((f) => <line key={f} x1={pad} x2={W} y1={H - H * f * 0.92} y2={H - H * f * 0.92} className="stroke-border" strokeDasharray="3 4" />)}
        {series.map((d, i) => {
          const x = pad + i * (bw + gap), hp = (d.passed / max) * H * 0.92, hf = (d.failed / max) * H * 0.92;
          return (
            <g key={d.date}>
              <title>{`${d.date}: ${d.passed} without problems, ${d.failed} with problems`}</title>
              <rect x={x} y={H - hp} width={bw} height={hp} rx={1.5} className="fill-ok" />
              <rect x={x} y={H - hp - hf} width={bw} height={hf} rx={1.5} className="fill-bad" />
              <rect x={x} y={0} width={bw} height={H} fill="transparent" />
            </g>
          );
        })}
        <text x={pad} y={H + 14} className="fill-muted-foreground text-[10px]">{first}</text>
        <text x={W} y={H + 14} textAnchor="end" className="fill-muted-foreground text-[10px]">{last}</text>
        <text x={0} y={12} className="fill-muted-foreground text-[10px]">{max}</text>
      </svg>
      <figcaption className="flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm bg-ok" />No problems</span>
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm bg-bad" />Problems found</span>
      </figcaption>
    </figure>
  );
}

const TONE_BG: Record<string, string> = { critical: "bg-bad", high: "bg-warn", medium: "bg-violet", low: "bg-brand", ok: "bg-ok", bad: "bg-bad", neutral: "bg-muted-foreground" };

/** Horizontal bars with the number at the end. */
export function HBars({ rows }: { rows: { label: string; value: number; tone: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-3 text-sm">
          <span className="capitalize text-muted-foreground">{r.label}</span>
          <span className="h-2.5 overflow-hidden rounded-full bg-muted"><span className={cn("block h-full rounded-full", TONE_BG[r.tone] ?? "bg-brand")} style={{ width: `${(r.value / max) * 100}%` }} /></span>
          <span className="text-right tabular-nums">{r.value}</span>
        </li>
      ))}
    </ul>
  );
}

const DOT: Record<string, string> = { passed: "bg-ok", failed: "bg-bad", error: "bg-bad", stopped: "bg-warn", running: "bg-brand", queued: "bg-muted-foreground", pending: "bg-muted-foreground" };

/** The last few runs of an app as coloured squares, oldest on the left. */
export function StatusStrip({ statuses }: { statuses: string[] }) {
  return (
    <span className="flex gap-0.5" role="img" aria-label={`Last ${statuses.length} runs: ${statuses.filter((s) => s === "passed").length} without problems`}>
      {[...statuses].reverse().map((s, i) => <i key={i} title={s} className={cn("h-4 w-1.5 rounded-sm", DOT[s] ?? "bg-muted-foreground")} />)}
    </span>
  );
}
