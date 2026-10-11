"use client";
import { HowItWorks } from "@/components/how-it-works";
import { ArrowRight, Globe, Plus } from "lucide-react";
import Link from "next/link";
import { Card, Empty, ErrorState, LinkButton, Loading, ago } from "@/components/ui";
import { useApps } from "@/lib/api/hooks";

export default function Home() {
  const { data, error, isPending, refetch } = useApps();
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your apps</h1>
          <p className="text-sm text-muted-foreground">QAgent tests websites the way a person would: it opens a real browser, clicks through your app, and tells you what is broken.</p>
        </div>
        <LinkButton href="/apps/new" variant="primary"><Plus className="size-4" />Add an app</LinkButton>
      </div>
      <HowItWorks />
      {isPending ? <Loading /> : error ? <ErrorState error={error} retry={refetch} /> : !data.length ? (
        <Empty title="Nothing to test yet" hint="Add the address of a website or web app. You will then describe what to test and let QAgent run it." action={<LinkButton href="/apps/new" variant="primary">Add your first app</LinkButton>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((a) => (
            <Link key={a.id} href={`/apps/${a.slug}`} className="group">
              <Card className="h-full p-5 transition group-hover:border-brand/50">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{a.name}</div>
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
