"use client";
import { CheckCircle2, Circle, Compass, MinusCircle, Play, SkipForward } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useSyncExternalStore } from "react";
import { Card, cn } from "@/components/ui";
import { useApp, usePlaybooks, useRuns } from "@/lib/api/hooks";
import { useFiles } from "@/lib/api/live";
import { emptyMemory, guideStates, markVisited, nextStep, progress, readMemory, skipStep, subscribeMemory, unskipStep, type StepState } from "@/lib/guide";

/** Everything the guide needs for one app: each step's state, what comes next, and how far along the user is. */
export function useGuide(slug: string) {
  const { data: app } = useApp(slug);
  const { data: plans } = usePlaybooks(slug);
  const { data: runs } = useRuns(slug);
  const { data: files } = useFiles(slug);
  const memory = useSyncExternalStore(subscribeMemory, () => readMemory(slug), () => emptyMemory);
  const states = useMemo(() => guideStates({ app, plans, runs, files, visited: memory.visited, skipped: memory.skipped }), [app, plans, runs, files, memory]);
  const latestRun = runs?.find((r) => r.status !== "queued")?.id;
  const next = nextStep(states);
  return { states, next, latestRun, ...progress(states), ready: !!app && !!plans && !!runs && !!files };
}

/** Marks "read what it found" as done once the user has opened a run or the bug list. */
export function GuideTracker({ slug }: { slug: string }) {
  const path = usePathname();
  useEffect(() => { if (/\/runs\/[^/]+/.test(path) || /\/issues(\/|$)/.test(path)) markVisited(slug, "results"); }, [path, slug]);
  return null;
}

const ICON: Record<StepState, typeof Circle> = { done: CheckCircle2, skipped: MinusCircle, todo: Circle };

/** The full step-by-step list, shown on the Overview. */
export function GuidePanel({ slug }: { slug: string }) {
  const g = useGuide(slug);
  if (!g.ready) return null;
  if (g.done === g.total) return null;
  const hrefFor = (id: string) => { const s = g.states.find((x) => x.step.id === id)!.step; return `${s.path(slug, g.latestRun)}${s.path(slug, g.latestRun).includes("?") ? "&" : "?"}guide=${id}`; };
  return (
    <Card className="overflow-hidden" data-tour="guide" aria-label="Setup guide">
      <div className="bg-hero on-blue flex flex-wrap items-center gap-3 px-5 py-4">
        <span className="grid size-10 place-items-center rounded-xl bg-white/15"><Compass className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold">Setup guide</h2>
          <p className="text-sm text-white/80">{g.done} of {g.total} steps done. Follow them in order; each one takes you to the right place and points at what to do.</p>
        </div>
        {g.next && <Link href={hrefFor(g.next.id)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"><Play className="size-4" />{g.done === 0 ? "Start the guide" : `Continue: ${g.next.title}`}</Link>}
      </div>
      <div className="h-1.5 bg-secondary"><div className="h-full bg-primary transition-all" style={{ width: `${(g.done / g.total) * 100}%` }} /></div>
      <ol className="divide-y">
        {g.states.map(({ step, state }, i) => {
          const Icon = ICON[state];
          return (
            <li key={step.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <Icon className={cn("size-5 shrink-0", state === "done" ? "text-ok" : "text-muted-foreground/70")} aria-hidden />
              <div className="min-w-0 flex-1">
                <div className={cn("text-sm font-medium", state !== "todo" && "text-muted-foreground")}>{i + 1}. {step.title}{step.optional && <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[11px] font-normal text-muted-foreground">optional</span>}<span className="sr-only"> ({state === "done" ? "done" : state === "skipped" ? "skipped" : "to do"})</span></div>
                <div className="text-xs text-muted-foreground">{step.why}</div>
              </div>
              {state === "todo" && <Link href={hrefFor(step.id)} className="rounded-lg border border-brand/25 bg-card px-3 py-1.5 text-sm text-secondary-foreground shadow-xs hover:bg-secondary">Take me there</Link>}
              {state === "todo" && step.optional && <button onClick={() => skipStep(slug, step.id)} className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted"><SkipForward className="size-3.5" />Skip</button>}
              {state === "skipped" && <button onClick={() => unskipStep(slug, step.id)} className="text-xs text-muted-foreground underline">Undo skip</button>}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

/** A small progress card for the app side panel. */
export function GuideProgress({ slug }: { slug: string }) {
  const g = useGuide(slug);
  if (!g.ready || g.done === g.total || !g.next) return null;
  const s = g.next;
  const href = `${s.path(slug, g.latestRun)}${s.path(slug, g.latestRun).includes("?") ? "&" : "?"}guide=${s.id}`;
  return (
    <Link href={href} data-tour="guide-progress" className="card-lift block rounded-xl border bg-gradient-to-br from-card to-secondary p-3 text-sm">
      <div className="flex items-center justify-between text-xs text-muted-foreground"><span className="flex items-center gap-1.5"><Compass className="size-3.5 text-brand" />Setup guide</span><span>{g.done}/{g.total}</span></div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary" style={{ width: `${(g.done / g.total) * 100}%` }} /></div>
      <div className="mt-2 font-medium leading-snug">Next: {s.title}</div>
    </Link>
  );
}
