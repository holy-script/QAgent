"use client";
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
          <h1 className="text-2xl font-semibold tracking-tight">Apps</h1>
          <p className="text-sm text-muted">Register a web app, attach Markdown playbooks, and run them.</p>
        </div>
        <LinkButton href="/apps/new" variant="primary"><Plus className="size-4" />New app</LinkButton>
      </div>
      {isPending ? <Loading /> : error ? <ErrorState error={error} retry={refetch} /> : !data.length ? (
        <Empty title="No apps yet" hint="Add the URL of the app you want to test to get started." action={<LinkButton href="/apps/new" variant="primary">Add your first app</LinkButton>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((a) => (
            <Link key={a.id} href={`/apps/${a.slug}`} className="group">
              <Card className="h-full p-5 transition group-hover:border-accent/50">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{a.name}</div>
                  <ArrowRight className="size-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-xs text-muted"><Globe className="size-3" />{a.base_url}</div>
                <p className="mt-3 line-clamp-2 text-sm text-muted">{a.description || "No description"}</p>
                <div className="mt-4 text-xs text-muted">Added {ago(a.created_at)}</div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
