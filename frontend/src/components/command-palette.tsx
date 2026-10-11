"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { api, http, USE_MOCK } from "@/lib/api/client";

interface Entry { id: string; label: string; hint: string; href: string; group: string }
const TABS: [string, string][] = [["", "Overview"], ["playbooks", "Test plans"], ["runs", "Runs"], ["flows", "Journeys"], ["issues", "Bugs found"], ["traceability", "Requirements"], ["compare", "Compare"], ["settings", "Settings"]];

/** Ctrl/Cmd+K: jump to any page, recent run, or bug. */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); } };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const { data: entries = [] } = useQuery({
    queryKey: ["palette"], enabled: open, staleTime: 15_000,
    queryFn: async (): Promise<Entry[]> => {
      const out: Entry[] = [{ id: "home", label: "All apps", hint: "home", href: "/", group: "Pages" }];
      for (const app of await api.listApps()) {
        for (const [t, name] of TABS) out.push({ id: `${app.slug}/${t}`, label: `${app.name}: ${name}`, hint: "page", href: `/apps/${app.slug}${t ? "/" + t : ""}`, group: "Pages" });
        for (const r of (await api.listRuns(app.slug)).slice(0, 5)) out.push({ id: r.id, label: `Run ${r.id.slice(0, 8)} · ${r.playbook_name} · ${r.status}`, hint: app.name, href: `/apps/${app.slug}/runs/${r.id}`, group: "Recent runs" });
        if (!USE_MOCK) {
          for (const i of await http<{ id: string; title: string; status: string }[]>(`/apps/${app.slug}/issues`)) out.push({ id: i.id, label: i.title, hint: i.status, href: `/apps/${app.slug}/issues/${i.id}`, group: "Bugs found" });
        }
      }
      return out;
    },
  });
  const groups = [...new Set(entries.map((e) => e.group))];

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Jump to an app page, a run or a bug">
      <Command>
        <CommandInput placeholder="Search pages, runs and bugs…" aria-label="Search" />
        <CommandList>
          <CommandEmpty>Nothing matches.</CommandEmpty>
          {groups.map((g) => (
            <CommandGroup key={g} heading={g}>
              {entries.filter((e) => e.group === g).map((e) => (
                <CommandItem key={e.id} value={`${e.label} ${e.hint}`} onSelect={() => { router.push(e.href); setOpen(false); }}>
                  <span className="truncate">{e.label}</span><span className="ml-auto text-xs text-muted-foreground">{e.hint}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          ))}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
