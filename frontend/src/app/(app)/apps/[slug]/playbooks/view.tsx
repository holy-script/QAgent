"use client";
import { FileText, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, Empty, ErrorState, LinkButton, Loading, StatusPill, ago } from "@/components/ui";
import { DeletePlan } from "@/components/delete-plan";
import { usePlaybooks } from "@/lib/api/hooks";

export default function Playbooks() {
  const { slug } = useParams<{ slug: string }>();
  const { data, error, isPending, refetch } = usePlaybooks(slug);
  const base = `/apps/${slug}/playbooks`;
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h2 className="font-medium">Test plans</h2><p className="text-sm text-muted-foreground">A test plan describes what QAgent should check: the journeys to walk through and what must be true afterwards.</p></div>
        <LinkButton href={`${base}/new`} variant="primary"><Plus className="size-4" />Add a test plan</LinkButton>
      </div>
      {!data.length ? (
        <Empty title="No test plans yet" hint="Write down what to test (or paste notes and let AI shape them), then run it. A sample is one click away." action={<LinkButton href={`${base}/new`} variant="primary">Add your first test plan</LinkButton>} />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {data.map((p) => {
            const v = p.versions[0];
            const errs = v.warnings.filter((w) => w.level === "error").length;
            return (
              <div key={p.id} className="group relative">
              <Link href={`${base}/${p.id}`}>
                <Card className="card-lift flex h-full gap-3 bg-gradient-to-br from-card to-secondary/50 p-4">
                  <FileText className="mt-0.5 size-5 shrink-0 text-brand" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2"><span className="truncate font-medium">{p.name}</span><StatusPill status={p.status} /></div>
                    <div className="mt-1 text-xs text-muted-foreground">Version {v.version_no} · {v.parsed.flows.length} journeys · updated {ago(v.created_at)}</div>
                    {errs > 0 && <div className="mt-2 text-xs text-bad">{errs} problem{errs > 1 ? "s" : ""} to fix before it can run</div>}
                  </div>
                </Card>
              </Link>
              <DeletePlan slug={slug} plan={p} icon className="absolute right-2 top-2 opacity-0 transition focus-visible:opacity-100 group-hover:opacity-100 max-md:opacity-100" />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
