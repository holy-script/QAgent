"use client";
import { driver, type DriveStep } from "driver.js";
import "driver.js/dist/driver.css";
import { CircleHelp } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useGuide } from "@/components/guide";
import { GUIDE_STEPS, nextStep } from "@/lib/guide";
import { TOURS, tourForPath, type TourDef } from "@/lib/tours";

const SEEN_KEY = "qagent_tours";
const seen = (): string[] => { try { return JSON.parse(localStorage.getItem(SEEN_KEY) ?? "[]"); } catch { return []; } };
const markSeen = (id: string) => { try { const s = seen(); if (!s.includes(id)) localStorage.setItem(SEEN_KEY, JSON.stringify([...s, id])); } catch { /* private mode */ } };

/** First element with this data-tour that is actually on screen (the side list and the tabs both exist; one is hidden). */
const visible = (name: string): HTMLElement | null =>
  Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`)).find((el) => el.getClientRects().length > 0) ?? null;

interface TourApi { start: (id?: string) => Promise<void> }
const Ctx = createContext<TourApi>({ start: async () => {} });
export const useTour = () => useContext(Ctx);

export function TourProvider({ children }: { children: ReactNode }) {
  const active = useRef<ReturnType<typeof driver> | null>(null);

  const start = useCallback(async (id?: string) => {
    const def: TourDef = TOURS[id ?? tourForPath(window.location.pathname)] ?? TOURS.home;
    active.current?.destroy();
    // Pages fill in as their data arrives: give targets up to two seconds to appear (hidden ones count as present).
    for (let i = 0; i < 20 && def.steps.some((s) => s.target && !document.querySelector(`[data-tour="${s.target}"]`)); i++) {
      await new Promise((r) => setTimeout(r, 100));
    }
    const steps: DriveStep[] = def.steps
      .filter((s) => !s.target || visible(s.target))
      .map((s) => ({ element: s.target ? () => visible(s.target!)! : undefined, popover: { title: s.title, description: s.text, side: s.side ?? "bottom", align: "start" as const } }));
    if (!steps.length) return;
    markSeen(def.id);
    const d = driver({
      steps, showProgress: true, allowClose: true, overlayOpacity: 0.55, stagePadding: 6, stageRadius: 10, popoverClass: "qagent-tour",
      nextBtnText: "Next", prevBtnText: "Back", doneBtnText: "Done", progressText: "{{current}} of {{total}}",
      onDestroyed: () => { active.current = null; },
    });
    active.current = d;
    d.drive();
  }, []);

  // ?tour=app starts a tour from a link (used by the Help page).
  const api = useMemo<TourApi>(() => ({ start }), [start]);
  return (
    <Ctx.Provider value={api}>
      {children}
      <Suspense fallback={null}><TourTriggers start={start} /></Suspense>
    </Ctx.Provider>
  );
}

/** Starts the home tour for a first-time visitor, offers the page tours once, and honours ?tour=. */
function TourTriggers({ start }: { start: (id?: string) => Promise<void> }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = params.get("tour");
  const guideId = params.get("guide");
  const slug = pathname.match(/^\/apps\/([^/]+)/)?.[1];
  if (guideId && slug && GUIDE_STEPS.some((s) => s.id === guideId)) return <GuideSpotlight key={`${slug}:${guideId}`} slug={slug} stepId={guideId} />;
  return <TourAuto pathname={pathname} requested={requested} start={start} />;
}

function TourAuto({ pathname, requested, start }: { pathname: string; requested: string | null; start: (id?: string) => Promise<void> }) {
  useEffect(() => {
    if (requested && TOURS[requested]) { const t = setTimeout(() => void start(requested), 600); return () => clearTimeout(t); }
    if (typeof navigator !== "undefined" && navigator.webdriver) return; // automated browsers (tests) are never interrupted
    const id = tourForPath(pathname);
    if (pathname.startsWith("/login") || pathname === "/help" || seen().includes(id)) return;
    const t = setTimeout(() => {
      if (id === "home") { void start("home"); return; }
      markSeen(id);
      toast(`New here? A 30-second tour of this page is available.`, { duration: 9000, action: { label: "Show me", onClick: () => void start(id) } });
    }, 1200);
    return () => clearTimeout(t);
  }, [pathname, requested, start]);
  return null;
}

/** Header button: replays the tour that fits the page you are on. */
export function TourButton() {
  const { start } = useTour();
  return (
    <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground" onClick={() => void start()} aria-label="Take a tour of this page" data-tour="tour-button">
      <CircleHelp className="size-3.5" /><span className="hidden sm:inline">Tour</span>
    </Button>
  );
}

/** The guided setup's pointer: waits for the step's target to appear, then points at it with "Next step". */
function GuideSpotlight({ slug, stepId }: { slug: string; stepId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const g = useGuide(slug);
  const started = useRef(false);
  const alive = useRef(true);
  const moving = useRef(false);
  const instance = useRef<ReturnType<typeof driver> | null>(null);
  // Leaving the page (for example pressing "Run now") must take the pointer down with it.
  useEffect(() => {
    alive.current = true;
    document.body.classList.add("guide-spotlight");
    return () => { alive.current = false; document.body.classList.remove("guide-spotlight"); instance.current?.destroy(); instance.current = null; };
  }, []);
  // If the user does the step the pointer is showing, the pointer has done its job.
  const doneNow = g.states.find((s) => s.step.id === stepId)?.state === "done";
  const wasDone = useRef<boolean | null>(null);
  useEffect(() => {
    if (!g.ready) return;
    // ("results" counts as done just by being on the page, so it must not dismiss itself)
    if (wasDone.current === false && doneNow && stepId !== "results") { moving.current = true; instance.current?.destroy(); instance.current = null; router.replace(pathname); }
    wasDone.current = doneNow;
  }, [doneNow, g.ready, router, pathname, stepId]);
  useEffect(() => {
    if (!g.ready || started.current) return;
    started.current = true;
    const step = GUIDE_STEPS.find((x) => x.id === stepId)!;
    const upcoming = nextStep(g.states, stepId);
    const welcome = g.done === 0 && stepId === "describe" ? "Welcome! Let's set your app up in a few steps. " : "";
    const close = () => router.replace(pathname);
    (async () => {
      for (let i = 0; i < 40 && !visible(step.target); i++) await new Promise((r) => setTimeout(r, 100));
      if (!alive.current) return;
      const el = visible(step.target);
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
      const d = driver({
        allowClose: true, overlayOpacity: 0.5, stagePadding: 8, stageRadius: 12, popoverClass: "qagent-tour", showProgress: false,
        steps: [{
          element: el ?? undefined,
          popover: {
            title: step.title, description: welcome + step.spotlight, side: "bottom", align: "start",
            showButtons: ["next", "close"], onCloseClick: () => { d.destroy(); close(); }, nextBtnText: upcoming ? `Next: ${upcoming.title} →` : "Done",
            onNextClick: () => {
              moving.current = true;
              d.destroy();
              if (upcoming) router.push(`${upcoming.path(slug, g.latestRun)}?guide=${upcoming.id}`); else close();
            },
          },
        }],
        onDestroyed: () => { if (alive.current && !moving.current) close(); },
      });
      instance.current = d;
      d.drive();
    })();
  }, [g, stepId, slug, router, pathname]);
  return null;
}
