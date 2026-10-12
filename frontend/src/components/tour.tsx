"use client";
import { driver, type DriveStep } from "driver.js";
import "driver.js/dist/driver.css";
import { CircleHelp } from "lucide-react";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
