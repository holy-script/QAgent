"use client";
import { useEffect, useRef, useState } from "react";
import { Empty, cn, fmtMs } from "@/components/ui";
import type { LogEntry } from "@/lib/api/types";
import type { RunView } from "@/lib/run-state";

const LEVELS: LogEntry["level"][] = ["debug", "info", "warn", "error"];
const COLOR: Record<LogEntry["level"], string> = { debug: "text-muted-foreground", info: "text-sky-300", warn: "text-warn", error: "text-bad" };

export function LogsTab({ view, live, onOpen }: { view: RunView; live: boolean; onOpen: (flow: string, seq: number) => void }) {
  const [min, setMin] = useState(0);
  const end = useRef<HTMLDivElement>(null);
  const rows = view.logs.filter((l) => LEVELS.indexOf(l.level) >= min);
  useEffect(() => { if (live) end.current?.scrollIntoView({ block: "nearest" }); }, [rows.length, live]);
  return (
    <div className="space-y-3">
      <div className="flex gap-1" role="group" aria-label="Minimum level">
        {LEVELS.map((l, i) => (
          <button key={l} aria-pressed={min === i} onClick={() => setMin(i)} className={cn("rounded-md border px-2.5 py-1 text-xs", min === i ? "border-brand bg-brand/10 text-brand" : "border-border text-muted-foreground hover:bg-foreground/5")}>{l}{i > 0 && "+"}</button>
        ))}
      </div>
      {!rows.length ? <Empty title="Nothing logged" hint="Warnings and errors from the agent and the browser appear here." /> : (
        <div className="max-h-[32rem] overflow-y-auto rounded-xl border border-border bg-muted p-3 font-mono text-xs leading-6">
          {rows.map((l) => (
            <div key={l.id} className="flex gap-3">
              <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">{fmtMs(l.ts)}</span>
              <span className={cn("w-12 shrink-0 uppercase", COLOR[l.level])}>{l.level}</span>
              <span className="w-20 shrink-0 text-violet">{l.source}</span>
              <span className="flex-1">{l.message}</span>
              {l.flow_key && l.step_seq != null && <button className="shrink-0 text-brand hover:underline" onClick={() => onOpen(l.flow_key!, l.step_seq!)}>{l.flow_key}·{l.step_seq}</button>}
            </div>
          ))}
          <div ref={end} />
        </div>
      )}
    </div>
  );
}
