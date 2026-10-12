// The guided setup: the order we recommend for a new app, how to tell each step is done, and where it happens.
import type { Credential, Playbook, Run, TestFile } from "@/lib/api/types";

export interface GuideStep {
  id: string;
  title: string;
  why: string;
  optional?: boolean;
  /** The page where the step happens. */
  path: (slug: string, runId?: string) => string;
  /** data-tour value of the thing to point at on that page. */
  target: string;
  /** Shown in the pointer on that page. */
  spotlight: string;
}

export const GUIDE_STEPS: GuideStep[] = [
  { id: "describe", title: "Describe your app", path: (s) => `/apps/${s}/settings`, target: "settings-prd",
    why: "Paste, import or dictate what the app is meant to do. This is what the tests are based on.",
    spotlight: "Tell QAgent what your app should do. Paste your product document, import a .md or .txt file, or press Dictate and just talk. “Organise with AI” turns rough words into a clear document. Save settings when you are done." },
  { id: "signin", title: "Add sign-in details", optional: true, path: (s) => `/apps/${s}/settings`, target: "signin-details",
    why: "Only if your app needs a login. Save it here, not in the test plan: it is stored encrypted and hidden in reports.",
    spotlight: "If your app needs a login, save the username and password here. Plans then say “Enter the username” and QAgent types the saved value in. Not needed? Skip this step." },
  { id: "files", title: "Add test files", optional: true, path: (s) => `/apps/${s}/settings`, target: "test-files",
    why: "Only if your app lets people upload files (a photo, a CSV, a PDF). Tests will attach these.",
    spotlight: "If your app has a file upload, add the files a test may attach here. QAgent already has small samples (png, pdf, txt, csv, json). Not needed? Skip this step." },
  { id: "plan", title: "Create a test plan", path: (s) => `/apps/${s}/playbooks/new`, target: "new-plan",
    why: "List the journeys to try (add to cart, pay) and what should be true afterwards.",
    spotlight: "Fastest: press “Create from product document” and AI writes high-level journeys (a goal and what should be true) from the document you added. Or start from the sample, upload a file, or dictate rough notes and press “Rewrite my notes as a test plan”. Then Save and review." },
  { id: "run", title: "Run your first test", path: (s) => `/apps/${s}`, target: "run-launcher",
    why: "QAgent opens a real browser and works through your plan. It takes about a minute.",
    spotlight: "Pick the test plan, keep Smart mode, and press Run now. You can watch it live." },
  { id: "results", title: "Read what it found", path: (s, r) => (r ? `/apps/${s}/runs/${r}` : `/apps/${s}/runs`), target: "run-tabs",
    why: "Each problem comes with screenshots, the server calls and steps to reproduce.",
    spotlight: "Your test is running. Watch it here, and when it finishes: Journeys shows every step, Problems lists what failed, and View report summarises everything. Open a bug for the full write-up." },
  { id: "repeat", title: "Fix, then repeat", optional: true, path: (s, r) => (r ? `/apps/${s}/runs/${r}` : `/apps/${s}/runs`), target: "repeat",
    why: "After a fix, run the same test again from the recording to confirm it.",
    spotlight: "“Repeat exactly” runs the same test again with no AI calls and no cost. Bugs that no longer appear are marked Fixed." },
];

export interface GuideInput { prd?: string; plans?: Playbook[]; runs?: Run[]; files?: TestFile[]; credentials?: Credential[]; visited: string[]; skipped: string[] }
export type StepState = "done" | "skipped" | "todo";

export function guideStates(i: GuideInput): { step: GuideStep; state: StepState }[] {
  const finished = (i.runs ?? []).filter((r) => r.status !== "running" && r.status !== "queued");
  const done: Record<string, boolean> = {
    describe: !!i.prd?.trim(),
    signin: (i.credentials?.length ?? 0) > 0,
    files: (i.files ?? []).some((f) => !f.builtin),
    plan: (i.plans?.length ?? 0) > 0,
    run: finished.length > 0,
    results: i.visited.includes("results"),
    repeat: (i.runs ?? []).some((r) => r.trigger === "replay"),
  };
  return GUIDE_STEPS.map((step) => ({ step, state: done[step.id] ? "done" : i.skipped.includes(step.id) ? "skipped" : "todo" }));
}

export const nextStep = (states: { step: GuideStep; state: StepState }[], after?: string) => {
  const from = after ? states.findIndex((s) => s.step.id === after) + 1 : 0;
  return [...states.slice(from), ...states.slice(0, from)].find((s) => s.state === "todo")?.step;
};

export const progress = (states: { state: StepState }[]) => ({ done: states.filter((s) => s.state !== "todo").length, total: states.length });

// Where the user is in the guide is remembered per app in this browser.
const key = (slug: string) => `qagent_guide_${slug}`;
export interface GuideMemory { visited: string[]; skipped: string[] }
const EMPTY: GuideMemory = { visited: [], skipped: [] };
const cache = new Map<string, { raw: string | null; value: GuideMemory }>();
const listeners = new Set<() => void>();

export function readMemory(slug: string): GuideMemory {
  let raw: string | null = null;
  try { raw = localStorage.getItem(key(slug)); } catch { /* private mode */ }
  const hit = cache.get(slug);
  if (hit && hit.raw === raw) return hit.value; // a stable object per stored value, as useSyncExternalStore needs
  let value = EMPTY;
  try { if (raw) value = { ...EMPTY, ...JSON.parse(raw) }; } catch { /* ignore */ }
  cache.set(slug, { raw, value });
  return value;
}
export const emptyMemory = EMPTY;
export function updateMemory(slug: string, fn: (m: GuideMemory) => GuideMemory) {
  const next = fn(readMemory(slug));
  try { localStorage.setItem(key(slug), JSON.stringify(next)); } catch { /* private mode */ }
  listeners.forEach((l) => l());
}
export const subscribeMemory = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
export const markVisited = (slug: string, id: string) => updateMemory(slug, (m) => (m.visited.includes(id) ? m : { ...m, visited: [...m.visited, id] }));
export const skipStep = (slug: string, id: string) => updateMemory(slug, (m) => (m.skipped.includes(id) ? m : { ...m, skipped: [...m.skipped, id] }));
export const unskipStep = (slug: string, id: string) => updateMemory(slug, (m) => ({ ...m, skipped: m.skipped.filter((x) => x !== id) }));
