"use client";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/components/ui";
import { api, USE_MOCK, http } from "@/lib/api/client";

interface Entry { id: string; label: string; hint: string; href: string }
const TABS = ["", "playbooks", "runs", "flows", "issues", "traceability", "compare", "settings"];

/** Ctrl/Cmd+K: jump to any app page, recent run, or open issue. */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); setQ(""); setCursor(0); }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  useEffect(() => { if (open) input.current?.focus(); }, [open]);

  const { data: entries = [] } = useQuery({
    queryKey: ["palette"], enabled: open, staleTime: 15_000,
    queryFn: async (): Promise<Entry[]> => {
      const out: Entry[] = [];
      for (const app of await api.listApps()) {
        for (const t of TABS) out.push({ id: `${app.slug}/${t}`, label: `${app.name}: ${t ? t[0].toUpperCase() + t.slice(1) : "Overview"}`, hint: "page", href: `/apps/${app.slug}${t ? "/" + t : ""}` });
        for (const r of (await api.listRuns(app.slug)).slice(0, 5)) out.push({ id: r.id, label: `Run ${r.id.slice(0, 8)} · ${r.playbook_name} · ${r.status}`, hint: app.name, href: `/apps/${app.slug}/runs/${r.id}` });
        if (!USE_MOCK) {
          for (const i of await http<{ id: string; title: string; status: string }[]>(`/apps/${app.slug}/issues`)) out.push({ id: i.id, label: i.title, hint: `issue · ${i.status}`, href: `/apps/${app.slug}/issues/${i.id}` });
        }
      }
      return out;
    },
  });
  const shown = useMemo(() => entries.filter((e) => `${e.label} ${e.hint}`.toLowerCase().includes(q.toLowerCase())).slice(0, 12), [entries, q]);
  const go = (e?: Entry) => { if (e) { router.push(e.href); setOpen(false); } };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/60 p-4 pt-[12vh]" onClick={() => setOpen(false)}>
      <div role="dialog" aria-label="Command palette" className="w-full max-w-xl overflow-hidden rounded-xl border border-line bg-background shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-4"><Search className="size-4 text-muted" />
          <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setCursor(0); }} placeholder="Jump to an app, run or issue…" aria-label="Search"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted/60"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, shown.length - 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
              if (e.key === "Enter") go(shown[cursor]);
            }} />
        </div>
        <ul role="listbox" className="max-h-80 overflow-y-auto py-1">
          {shown.map((e, i) => (
            <li key={e.id} role="option" aria-selected={i === cursor} onMouseEnter={() => setCursor(i)} onClick={() => go(e)}
              className={cn("flex cursor-pointer items-center gap-3 px-4 py-2 text-sm", i === cursor && "bg-accent/15")}>
              <span className="min-w-0 flex-1 truncate">{e.label}</span><span className="text-xs text-muted">{e.hint}</span>
            </li>
          ))}
          {!shown.length && <li className="px-4 py-6 text-center text-sm text-muted">Nothing matches.</li>}
        </ul>
      </div>
    </div>
  );
}
