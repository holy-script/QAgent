"use client";
import { Fragment, useState } from "react";
import { Badge, Empty, cn, fmtBytes, fmtMs } from "@/components/ui";
import { CallBodies } from "@/components/live/call-bodies";
import { USE_MOCK } from "@/lib/api/client";
import type { RunView } from "@/lib/run-state";

export function NetworkTab({ view, onOpen }: { view: RunView; onOpen: (flow: string, seq: number) => void }) {
  const [apiOnly, setApiOnly] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const rows = view.network.filter((n) => !apiOnly || n.is_api);
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={apiOnly} onChange={(e) => setApiOnly(e.target.checked)} />Only calls the app makes to its server (hide page and image loads)</label>
      {!rows.length ? <Empty title="No server calls yet" hint="Calls appear as the app talks to its server." /> : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-foreground/[0.03] text-xs uppercase tracking-wide text-muted-foreground">
              <tr>{["Journey · step", "Method", "Address", "Status", "Time", "Size sent / received"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-border font-mono text-xs">
              {rows.map((c) => (
                <Fragment key={c.id}>
                  <tr className={cn("cursor-pointer hover:bg-foreground/[0.03]", c.status >= 400 && "bg-bad/5")} onClick={() => setOpen(open === c.id ? null : c.id)}>
                    <td className="px-4 py-2"><button className="text-brand hover:underline" onClick={(e) => { e.stopPropagation(); onOpen(c.flow_key, c.step_seq); }}>{c.flow_key} · {c.step_seq}</button></td>
                    <td className="px-4 py-2">{c.method}</td>
                    <td className="max-w-xs truncate px-4 py-2">{c.url}</td>
                    <td className="px-4 py-2"><Badge tone={c.status >= 400 ? "bad" : "ok"}>{c.status}</Badge></td>
                    <td className={cn("px-4 py-2 tabular-nums", c.duration_ms > 2000 && "text-warn")}>{fmtMs(c.duration_ms)}</td>
                    <td className="px-4 py-2 tabular-nums text-muted-foreground">{fmtBytes(c.req_size)} ↑ {fmtBytes(c.resp_size)} ↓</td>
                  </tr>
                  {open === c.id && (
                    <tr><td colSpan={6} className="bg-muted px-4 py-3">
                      {USE_MOCK ? (
                        <div className="grid gap-3 md:grid-cols-2">
                          <Body title="Request" body={c.request_body} /><Body title="Response" body={c.response_body} />
                        </div>
                      ) : <CallBodies callId={c.id} />}
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const Body = ({ title, body }: { title: string; body: unknown }) => (
  <div><div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>
    <pre className="max-h-48 overflow-auto rounded bg-code p-2 text-[11px]">{body === undefined ? "(no body captured)" : JSON.stringify(body, null, 2)}</pre></div>
);
