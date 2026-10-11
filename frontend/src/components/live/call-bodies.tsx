"use client";
import { useQuery } from "@tanstack/react-query";
import { http } from "@/lib/api/client";
import { assetUrl } from "@/lib/api/live";
import type { components } from "@/lib/api/schema";

type Detail = components["schemas"]["NetworkCallDetail"];

async function fetchBody(path: string | null | undefined): Promise<unknown> {
  if (!path) return undefined;
  const res = await fetch(assetUrl(path), { credentials: "include" });
  if (!res.ok) return undefined;
  const text = await res.text();
  try { return JSON.parse(text); } catch { return text; }
}

/** Request and response bodies of one recorded call, side by side. Bodies are fetched on demand through the API proxy. */
export function CallBodies({ callId }: { callId: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["call-bodies", callId],
    queryFn: async () => {
      const d = await http<Detail>(`/network/${callId}`);
      const [req, res] = await Promise.all([fetchBody(d.req_body_url), fetchBody(d.resp_body_url)]);
      return { detail: d, req, res };
    },
  });
  if (isPending) return <div className="text-xs text-muted-foreground">Loading bodies…</div>;
  return (
    <div className="space-y-2">
      <div className="grid gap-3 md:grid-cols-2">
        <Body title="Request" body={data?.req} />
        <Body title="Response" body={data?.res} />
      </div>
      {data?.detail.traceparent && <div className="font-mono text-[11px] text-muted-foreground">traceparent {data.detail.traceparent}</div>}
    </div>
  );
}

const Body = ({ title, body }: { title: string; body: unknown }) => (
  <div>
    <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>
    <pre className="max-h-56 overflow-auto rounded bg-code p-2 text-[11px]">
      {body === undefined ? "(no body captured)" : typeof body === "string" ? body : JSON.stringify(body, null, 2)}
    </pre>
  </div>
);
