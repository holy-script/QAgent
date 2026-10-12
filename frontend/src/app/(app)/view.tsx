"use client";
import { Dashboard } from "@/components/dashboard/dashboard";
import { HowItWorks } from "@/components/how-it-works";
import { ArrowRight, Globe, Plus } from "lucide-react";
import Link from "next/link";
import { Card, Empty, ErrorState, LinkButton, Loading, ago } from "@/components/ui";
import { useApps } from "@/lib/api/hooks";

export default function Home() {
  const { data, error, isPending, refetch } = useApps();
  return (
    <div className="space-y-6">
      <div className="bg-hero relative flex flex-wrap items-center justify-between gap-4 overflow-hidden rounded-2xl px-6 py-7 shadow-(--shadow-card) sm:px-8">
        <div className="max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight">Your apps</h1>
          <p className="mt-1.5 text-sm text-white/85 sm:text-base">QAgent tests websites the way a person would: it opens a real browser, clicks through your app, and tells you what is broken.</p>
        </div>
        <LinkButton href="/apps/new" variant="primary" data-tour="add-app" className="h-10 px-4 text-sm shadow-md"><Plus className="size-4" />Add an app</LinkButton>
      </div>
      <Dashboard />
      {isPending ? <Loading /> : error ? <ErrorState error={error} retry={refetch} /> : !data.length ? (
        <><HowItWorks /><Empty title="Nothing to test yet" hint="Add the address of a website or web app. You will then describe what to test and let QAgent run it." action={<LinkButton href="/apps/new" variant="primary">Add your first app</LinkButton>} /></>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" data-tour="app-list">
          {data.map((a) => (
            <Link key={a.id} href={`/apps/${a.slug}`} className="group">
              <Card className="card-lift h-full bg-gradient-to-br from-card to-secondary/60 p-5">
                <div className="flex items-center justify-between gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-sm font-bold text-primary-foreground">{a.name.slice(0, 2).toUpperCase()}</span>
                  <div className="min-w-0 flex-1 truncate font-semibold">{a.name}</div>
                  <ArrowRight className="size-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-brand" />
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><Globe className="size-3" />{a.base_url}</div>
                <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{a.description || "No description yet"}</p>
                <div className="mt-4 text-xs text-muted-foreground">Added {ago(a.created_at)}</div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
