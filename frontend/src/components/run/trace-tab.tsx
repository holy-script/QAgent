"use client";
import { Empty, cn, fmtMs } from "@/components/ui";
import type { Span } from "@/lib/api/types";
import type { RunView } from "@/lib/run-state";

const KIND_COLOR: Record<Span["kind"], string> = {
  run: "bg-muted-foreground", flow: "bg-violet", step: "bg-brand", decide: "bg-brand", act: "bg-ok", verify: "bg-ok",
};

export function TraceTab({ view }: { view: RunView }) {
  if (!view.spans.length) return <Empty title="No timeline yet" hint="Each bar shows how long a part of the run took. Bars appear as steps complete." />;
  const byId = new Map(view.spans.map((s) => [s.span_id, s]));
  const depth = (s: Span): number => (s.parent_span_id && byId.get(s.parent_span_id) ? 1 + depth(byId.get(s.parent_span_id)!) : 0);
  const end = Math.max(...view.spans.map((s) => s.end_ms), 1);
  // Parents before children, then by start time.
  const rows = [...view.spans].sort((a, b) => a.start_ms - b.start_ms || depth(a) - depth(b));
  return (
    <div className="space-y-1 rounded-xl border border-border p-3">
      <div className="flex justify-between px-[16rem] text-[11px] text-muted-foreground"><span>0</span><span>{fmtMs(end / 2)}</span><span>{fmtMs(end)}</span></div>
      {rows.map((s) => {
        const left = (s.start_ms / end) * 100, width = Math.max(((s.end_ms - s.start_ms) / end) * 100, 0.4);
        return (
          <div key={s.span_id} className="flex items-center gap-3 text-xs">
            <div className="w-[15rem] shrink-0 truncate" style={{ paddingLeft: depth(s) * 14 }} title={s.name}>{s.name}</div>
            <div className="relative h-5 flex-1 rounded bg-white/[0.04]">
              <div className={cn("absolute h-full rounded", s.status === "error" ? "bg-bad" : KIND_COLOR[s.kind])} style={{ left: `${left}%`, width: `${width}%` }}
                title={`${s.name} · ${fmtMs(s.end_ms - s.start_ms)}`} />
            </div>
            <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">{fmtMs(s.end_ms - s.start_ms)}</span>
          </div>
        );
      })}
    </div>
  );
}
