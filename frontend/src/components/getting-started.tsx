"use client";
import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui";
import { useApp, usePlaybooks, useRuns } from "@/lib/api/hooks";
import { useIssues } from "@/lib/api/live";
import { USE_MOCK } from "@/lib/api/client";

/** A four-step checklist that disappears once the user has done everything (or dismissed by completing it). */
export function GettingStarted({ slug }: { slug: string }) {
  const { data: app } = useApp(slug);
  const { data: plans } = usePlaybooks(slug);
  const { data: runs } = useRuns(slug);
  const { data: issues } = useIssues(slug);
  const finished = (runs ?? []).filter((r) => r.status !== "running" && r.status !== "queued");
  const hasProblems = finished.some((r) => r.totals.findings > 0);
  const steps = [
    { done: !!app, title: "Add your app", text: "Tell QAgent where it lives.", href: undefined },
    { done: (plans?.length ?? 0) > 0, title: "Write a test plan", text: "Describe the journeys to try and what should be true afterwards.", href: `/apps/${slug}/playbooks/new` },
    { done: finished.length > 0, title: "Run it", text: "QAgent clicks through your app in a real browser. Use “Run a test” on this page.", href: undefined },
    { done: (finished.length > 0 && !hasProblems) || (issues?.length ?? 0) > 0 || (USE_MOCK && hasProblems), title: "Review what it found", text: "Each problem comes with screenshots and proof. The same problem across runs is tracked as one bug.", href: `/apps/${slug}/issues` },
  ];
  if (steps.every((s) => s.done) && finished.length > 2) return null;
  return (
    <Card className="p-5">
      <div className="font-medium">Getting started</div>
      <p className="mb-4 text-sm text-muted-foreground">Four steps from nothing to a list of real bugs.</p>
      <ol className="grid gap-3 md:grid-cols-4">
        {steps.map((s, i) => {
          const body = (
            <div className="flex gap-2.5">
              {s.done ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-ok" /> : <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground/60" />}
              <div><div className="text-sm font-medium">{i + 1}. {s.title}</div><div className="text-xs text-muted-foreground">{s.text}</div></div>
            </div>
          );
          return <li key={s.title}>{s.href && !s.done ? <Link href={s.href} className="block rounded-lg p-2 hover:bg-muted">{body}</Link> : <div className="p-2">{body}</div>}</li>;
        })}
      </ol>
    </Card>
  );
}
