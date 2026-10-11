"use client";
import { useQuery } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import { ErrorState, Loading, Tabs } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useApp } from "@/lib/api/hooks";
import { useIssues } from "@/lib/api/live";

// useParams() is request-time data; with cacheComponents it must sit under a Suspense boundary.
export default function AppLayout({ children }: { children: ReactNode }) {
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
  return (
    <div className="space-y-5">
      {live && (
        <Link href={`${base}/runs/${live.id}`} className="flex items-center gap-3 rounded-xl border border-accent/40 bg-accent/10 px-4 py-2.5 text-sm hover:bg-accent/15">
          <span className="size-2 rounded-full bg-accent pulse-ring" />
          <span><b>Run in progress</b> · {live.playbook_name} · {live.mode}</span>
          <span className="ml-auto text-accent">Watch live →</span>
        </Link>
      )}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{app.name}</h1>
        <div className="mt-1 flex items-center gap-1.5 text-sm text-muted"><Globe className="size-3.5" />{app.base_url}</div>
      </div>
      <Tabs tabs={[
        { href: base, label: "Overview", exact: true },
        { href: `${base}/playbooks`, label: "Playbooks" },
        { href: `${base}/runs`, label: "Runs", count: runs?.length },
        { href: `${base}/flows`, label: "Flows" },
        { href: `${base}/issues`, label: "Issues", count: openIssues?.length },
        { href: `${base}/traceability`, label: "Traceability" },
        { href: `${base}/compare`, label: "Compare" },
        { href: `${base}/settings`, label: "Settings" },
      ]} />
      {children}
    </div>
  );
}
