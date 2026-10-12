"use client";
import { useQuery } from "@tanstack/react-query";
import { Bug, FileText, GitCompare, Globe, LayoutDashboard, ListChecks, Play, Route, Settings } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import { ErrorState, Loading, SideNav, Tabs, type NavItem } from "@/components/ui";
import { GuideProgress, GuideTracker } from "@/components/guide";
import { api } from "@/lib/api/client";
import { useApp } from "@/lib/api/hooks";
import { useIssues } from "@/lib/api/live";

// useParams() is request-time data; with cacheComponents it must sit under a Suspense boundary.
export function AppShellLayout({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Loading />}><AppShell>{children}</AppShell></Suspense>;
}

function AppShell({ children }: { children: ReactNode }) {
  const { slug } = useParams<{ slug: string }>();
  const { data: app, error, isPending, refetch } = useApp(slug);
  // Poll only while something is running; the banner is the app-wide "a run is live" signal.
  const { data: runs } = useQuery({ queryKey: ["runs", slug], queryFn: () => api.listRuns(slug), refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false) });
  const live = runs?.find((r) => r.status === "running");
  const { data: openIssues } = useIssues(slug, "open");

  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  const base = `/apps/${slug}`;
  const items: NavItem[] = [
    { href: base, label: "Overview", exact: true, icon: LayoutDashboard, tour: "nav-overview" },
    { href: `${base}/playbooks`, label: "Test plans", icon: FileText, tour: "nav-plans" },
    { href: `${base}/runs`, label: "Runs", count: runs?.length, icon: Play, tour: "nav-runs" },
    { href: `${base}/flows`, label: "Journeys", icon: Route, tour: "nav-journeys" },
    { href: `${base}/issues`, label: "Bugs", count: openIssues?.length, icon: Bug, tour: "nav-bugs" },
    { href: `${base}/traceability`, label: "Requirements", icon: ListChecks, tour: "nav-requirements" },
    { href: `${base}/compare`, label: "Compare", icon: GitCompare, tour: "nav-compare" },
    { href: `${base}/settings`, label: "Settings", icon: Settings, tour: "nav-settings" },
  ];
  return (
    // On wide screens the sections move to a side list, so the page gets the full height and more width.
    <div className="lg:grid lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-8">
      <GuideTracker slug={slug} />
      <aside className="hidden lg:block">
        <div className="sticky top-20 overflow-hidden rounded-2xl border bg-gradient-to-b from-secondary to-card shadow-(--shadow-card)">
          <div className="bg-hero on-blue flex items-center gap-3 px-4 py-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-sm font-bold text-primary-foreground shadow">{app.name.slice(0, 2).toUpperCase()}</span>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold leading-tight">{app.name}</h1>
              <div className="mt-0.5 flex items-center gap-1 text-[11px] text-white/90"><Globe className="size-3 shrink-0" /><span className="truncate">{app.base_url}</span></div>
            </div>
          </div>
          <div className="p-2"><SideNav items={items} /></div>
          <div className="border-t p-2"><GuideProgress slug={slug} /></div>
        </div>
      </aside>
      <div className="min-w-0 space-y-5">
        {live && (
          <Link href={`${base}/runs/${live.id}`} className="flex items-center gap-3 rounded-xl border border-brand/40 bg-brand/10 px-4 py-2.5 text-sm hover:bg-brand/15">
            <span className="size-2 rounded-full bg-brand pulse-ring" />
            <span><b>A test run is in progress</b> · {live.playbook_name}</span>
            <span className="ml-auto text-brand">Watch it live →</span>
          </Link>
        )}
        <div className="space-y-4 lg:hidden">
          <div className="bg-hero on-blue flex items-center gap-3 rounded-2xl px-4 py-4 shadow-(--shadow-card)">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary text-sm font-bold text-primary-foreground shadow">{app.name.slice(0, 2).toUpperCase()}</span>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold tracking-tight">{app.name}</h1>
              <div className="flex items-center gap-1.5 text-sm text-white/90"><Globe className="size-3.5 shrink-0" /><span className="truncate">{app.base_url}</span></div>
            </div>
          </div>
          <Tabs tabs={items} />
          <GuideProgress slug={slug} />
        </div>
        {children}
      </div>
    </div>
  );
}
