"use client";
import { Fragment, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge, Empty, SimpleTable, TableCell, TableRow, cn, fmtBytes, fmtMs } from "@/components/ui";
import { CallBodies } from "@/components/live/call-bodies";
import { USE_MOCK } from "@/lib/api/client";
import type { RunView } from "@/lib/run-state";

export function NetworkTab({ view, onOpen }: { view: RunView; onOpen: (flow: string, seq: number) => void }) {
  const [apiOnly, setApiOnly] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const rows = view.network.filter((n) => !apiOnly || n.is_api);
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm text-muted-foreground"><Checkbox checked={apiOnly} onCheckedChange={(c) => setApiOnly(!!c)} />Only calls the app makes to its server (hide page and image loads)</label>
      {!rows.length ? <Empty title="No server calls yet" hint="Calls appear as the app talks to its server." /> : (
        <SimpleTable className="font-mono text-xs" head={["Journey · step", "Method", "Address", "Status", "Time", "Size sent / received"]}>
              {rows.map((c) => (
                <Fragment key={c.id}>
                  <TableRow className={cn("cursor-pointer hover:bg-foreground/[0.03]", c.status >= 400 && "bg-bad/5")} onClick={() => setOpen(open === c.id ? null : c.id)}>
                    <TableCell className="px-4 py-2"><button className="text-brand hover:underline" onClick={(e) => { e.stopPropagation(); onOpen(c.flow_key, c.step_seq); }}>{c.flow_key} · {c.step_seq}</button></TableCell>
                    <TableCell className="px-4 py-2">{c.method}</TableCell>
                    <TableCell className="max-w-xs truncate px-4 py-2">{c.url}</TableCell>
                    <TableCell className="px-4 py-2"><Badge tone={c.status >= 400 ? "bad" : "ok"}>{c.status}</Badge></TableCell>
                    <TableCell className={cn("px-4 py-2 tabular-nums", c.duration_ms > 2000 && "text-warn")}>{fmtMs(c.duration_ms)}</TableCell>
                    <TableCell className="px-4 py-2 tabular-nums text-muted-foreground">{fmtBytes(c.req_size)} ↑ {fmtBytes(c.resp_size)} ↓</TableCell>
                  </TableRow>
                  {open === c.id && (
                    <TableRow><TableCell colSpan={6} className="bg-muted px-4 py-3">
                      {USE_MOCK ? (
                        <div className="grid gap-3 md:grid-cols-2">
                          <Body title="Request" body={c.request_body} /><Body title="Response" body={c.response_body} />
                        </div>
                      ) : <CallBodies callId={c.id} />}
                    </TableCell></TableRow>
                  )}
                </Fragment>
              ))}
        </SimpleTable>
      )}
    </div>
  );
}

const Body = ({ title, body }: { title: string; body: unknown }) => (
  <div><div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>
    <pre className="max-h-48 overflow-auto rounded bg-code p-2 text-[11px]">{body === undefined ? "(no body captured)" : JSON.stringify(body, null, 2)}</pre></div>
);
