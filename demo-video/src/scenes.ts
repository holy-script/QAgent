import { ClipSpec } from "./Camera";
import { InfoItem } from "./Cards";

export type Line = { text: string; start: number; end: number };
export type Timing = { id: string; seconds: number; lines: Line[] }[];
export type Shot = { from: number; clip?: ClipSpec; info?: { title: string; items: InfoItem[]; cols?: number }; outro?: boolean; logo?: boolean; tag?: string; stack?: { items: { text: string; at: number }[] } };
export type Overlay = { at: number; dur: number; text: string; sub?: string; color?: string };
export type SceneDef = { id: string; chapter: string; shots: Shot[]; overlays?: Overlay[]; tail?: number; noSubs?: boolean };

export const INTRO = 2.0, GAP = 0.55;
const W = { x: 960, y: 540, s: 1 };
const eco = (start: number, rate: number, keys: ClipSpec["keys"], callouts: ClipSpec["callouts"] = []): ClipSpec => ({ src: "eco_app.mp4", start, rate, keys, callouts });
const qa = (src: string, start: number, rate: number, keys: ClipSpec["keys"], callouts: ClipSpec["callouts"] = []): ClipSpec => ({ src, start, rate, keys, callouts });
const RED = "#ff6b5e";

export function buildScenes(tm: Timing): SceneDef[] {
  const T = (id: string) => tm.find((x) => x.id === id)!.lines.map((l) => l.start);   // line start times for a scene
  const h = T("hook"), m = T("meet"), s = T("setup"), p = T("plan"), q = T("quick"), r = T("run"), f = T("find"), b = T("bugs"), v = T("value"), n = T("next");
  return [
    { id: "hook", chapter: "The problem", shots: [
      { from: 0, clip: eco(74.2, 0.5, [{ t: 0, ...W }, { t: 4, fit: "kpirow", pad: 40 }], [{ track: "kpirow", at: 1.0, dur: 3.4, label: "ForecastIQ · Ocrevus · 12-month forecast", spot: true }]) },
      { from: h[1], tag: "Sped up", clip: eco(17, 3.4, [{ t: 0, ...W }, { t: 5, x: 1100, y: 560, s: 1.15 }]) },
      { from: h[2], stack: { items: [{ text: "Manual regression is slow", at: 0.2 }, { text: "Scripted tests break when pages change", at: 3.0 }, { text: "Bugs arrive without proof", at: 6.6 }] }, clip: eco(42, 0.7, [{ t: 0, ...W }, { t: 9, x: 960, y: 560, s: 1.05 }]) },
      { from: h[3], clip: eco(74.5, 0.5, [{ t: 0, fit: "kpirow", pad: 40 }, { t: 5, fit: "kpirow", pad: 40 }], [{ track: "kpirow", at: 0.4, dur: 5, label: "6,786 → 6,889. Looks fine.", spot: true }]) },
    ], overlays: [{ at: h[3] + 2.6, dur: 2.8, text: "But is it right?", color: "#ffd27a" }] },

    { id: "meet", chapter: "Meet QAgent", shots: [
      { from: 0, logo: true },
      { from: m[1], info: { title: "QAgent in one line", cols: 3, items: [{ big: "Plain English in", small: "Describe what the product must do", at: 0.5 }, { big: "A real browser", small: "An AI drives it like a careful person", at: 4.6 }, { big: "Proof out", small: "Every bug with screenshots and server calls", at: 8.6 }] } },
      { from: m[2], clip: eco(0.6, 0.35, [{ t: 0, x: 960, y: 520, s: 1.35 }, { t: 7, x: 960, y: 520, s: 1.35 }]) },
    ] },

    { id: "setup", chapter: "Step 1 · Set up an app", shots: [
      { from: 0, clip: qa("qa_setup.mp4", 6.2, 1.4, [{ t: 0, x: 960, y: 330, s: 1.5 }, { t: 3, x: 960, y: 330, s: 1.5 }]) },
      { from: s[1], clip: qa("qa_setup.mp4", 34.7, 1, [{ t: 0, fit: "signin", pad: 90 }, { t: 9, fit: "signin", pad: 90 }], [{ track: "signin", at: 1.2, dur: 7.5, label: "Saved once · encrypted · hidden from the AI", pad: 10 }]) },
      { from: s[2], clip: qa("qa_setup.mp4", 38, 1, [{ t: 0, fit: "testfiles", pad: 70 }, { t: 7, fit: "testfiles", pad: 70 }], [{ track: "testfiles", at: 0.5, dur: 6.5, label: "Clean files, and deliberately broken ones", pad: 10 }]) },
    ] },

    { id: "plan", chapter: "Step 2 · A plan from the PRD", shots: [
      { from: 0, clip: qa("qa_plan.mp4", 4.2, 1, [{ t: 0, ...W }, { t: 2, x: 960, y: 420, s: 1.2 }]) },
      { from: p[1], tag: "Sped up 3×", clip: qa("qa_plan.mp4", 8.5, 3.2, [{ t: 0, x: 960, y: 420, s: 1.25 }, { t: 7, x: 960, y: 420, s: 1.25 }]) },
      { from: p[2], clip: qa("qa_plan.mp4", 38, 0.75, [{ t: 0, x: 900, y: 360, s: 1.35 }, { t: 6.5, x: 900, y: 440, s: 1.35 }]) },
      { from: p[2] + 7.2, clip: qa("qa_plan.mp4", 64.4, 1, [{ t: 0, fit: "jcol", pad: 20 }, { t: 7, fit: "jcard_sign", pad: 80 }], [{ track: "jcard_sign", at: 1.2, dur: 5.5, label: "A goal, not click-by-click steps" }]) },
      { from: p[3], clip: qa("qa_plan.mp4", 64.4, 1, [{ t: 0, fit: "jcard_clean", pad: 50 }, { t: 7, fit: "jcard_clean", pad: 50 }], [{ track: "nums", at: 1.0, dur: 6.5, label: "Expected numbers, checked by code", spot: true, pad: 6 }]) },
    ] },

    { id: "quick", chapter: "Test just one flow", shots: [
      { from: 0, clip: qa("qa_quick.mp4", 3, 1, [{ t: 0, ...W }, { t: 2.5, x: 960, y: 330, s: 1.3 }]) },
      { from: q[1], tag: "Sped up 3×", clip: qa("qa_quick.mp4", 11.5, 2.9, [{ t: 0, fit: "editor", pad: 60 }, { t: 7, fit: "editor", pad: 60 }], [{ track: "editor", at: 0.5, dur: 6.5, label: "Plain notes about one story", pad: 8 }]) },
      { from: q[2], clip: qa("qa_quick.mp4", 38.5, 1.5, [{ t: 0, x: 960, y: 520, s: 1.3 }, { t: 7, x: 960, y: 640, s: 1.3 }], [{ track: "diff", at: 0.4, dur: 6, label: "Review every change before it is saved", pad: 4 }]) },
      { from: q[3], clip: qa("qa_quickrun.mp4", 20, 1.5, [{ t: 0, fit: "k_steps", pad: 330 }, { t: 5, fit: "k_steps", pad: 330 }], [{ track: "k_steps", at: 0.6, dur: 4.2, label: "One journey, tested in about a minute" }]) },
    ] },

    { id: "run", chapter: "Step 3 · Run it", shots: [
      { from: 0, clip: qa("qa_quick.mp4", 72, 0.7, [{ t: 0, x: 1610, y: 440, s: 1.7 }, { t: 10.5, x: 1610, y: 440, s: 1.7 }], [{ track: "runpanel", at: 1.0, dur: 9, label: "Smart · Thorough · Practice: you choose how it thinks", pad: 4 }]) },
      { from: r[1], tag: "Sped up 4×", clip: qa("qa_quick.mp4", 86, 4, [{ t: 0, x: 960, y: 420, s: 1.2 }, { t: 14, x: 960, y: 700, s: 1.2 }], [{ track: "k_steps", at: 3.2, dur: 5, label: "Every step is recorded as it happens" }]) },
    ] },

    { id: "find", chapter: "What it found", shots: [
      { from: 0, clip: qa("qa_results.mp4", 0.8, 1, [{ t: 0, ...W }, { t: 3, fit: "k_problems", pad: 220 }], [{ track: "k_problems", at: 1.2, dur: 2.2, label: "12 problems" }]) },
      { from: f[1], clip: qa("qa_results.mp4", 0.8, 1, [{ t: 0, x: 960, y: 220, s: 1.45 }, { t: 10, x: 960, y: 220, s: 1.45 }], [{ track: "k_steps", at: 1.2, dur: 3, label: "65 steps" }, { track: "k_problems", at: 4.4, dur: 3, label: "12 problems", color: RED }, { track: "k_cost", at: 7.4, dur: 3, label: "$1.50 for the full run" }]) },
      { from: f[2], clip: qa("qa_results.mp4", 25.5, 1, [{ t: 0, x: 1700, y: 400, s: 2.2 }, { t: 6.4, x: 1700, y: 400, s: 2.2 }], [{ track: "proofimg", at: 1.0, dur: 3, label: "Server says no (HTTP 422)", color: RED, pad: 6 }, { track: "proofimg", at: 3.8, dur: 2.6, label: "…the screen shows a forecast", color: RED, pad: 6 }]) },
      { from: f[3], clip: qa("qa_results.mp4", 32.2, 1, [{ t: 0, fit: "pexport", pad: 80 }, { t: 2.6, fit: "pexport", pad: 80 }], [{ track: "pexport", at: 0.2, dur: 2.4, label: "No download. No server request.", color: RED, pad: 6 }]) },
      { from: f[4], clip: eco(52.5, 1, [{ t: 0, fit: "bestfit", pad: 160 }, { t: 3.6, fit: "bestfit", pad: 160 }], [{ track: "bestfit", at: 0.3, dur: 3.3, label: "Flat 0% curve ranked “Best Fit”", color: RED, pad: 6 }]) },
      { from: f[5], clip: qa("qa_plan.mp4", 64.4, 1, [{ t: 0, fit: "jcard_clean", pad: 50 }, { t: 5.5, fit: "jcard_clean", pad: 50 }], [{ track: "nums", at: 0.5, dur: 5, label: "Checked by code, not by AI opinion", spot: true, pad: 6 }]) },
    ] },

    { id: "bugs", chapter: "Track, fix, replay", shots: [
      { from: 0, clip: qa("qa_bugs.mp4", 0.8, 1.5, [{ t: 0, ...W }, { t: 4, fit: "filters", pad: 260 }, { t: 9, ...W }], [{ track: "filters", at: 0.6, dur: 5, label: "Open · Came back · Fixed" }]) },
      { from: b[1], clip: qa("qa_bugs.mp4", 41.5, 1, [{ t: 0, fit: "repeat", pad: 260 }, { t: 6.5, fit: "repeat", pad: 260 }], [{ track: "repeat", at: 0.6, dur: 6, label: "Replays the recording. No model calls, no cost." }]) },
      { from: b[2], clip: qa("qa_bugs.mp4", 26, 1.9, [{ t: 0, fit: "reqkpi", pad: 160 }, { t: 4.4, x: 960, y: 540, s: 1.1 }]) },
    ] },

    { id: "value", chapter: "Business value", shots: [
      { from: 0, info: { title: "The full ForecastIQ run", cols: 2, items: [{ big: "~10 minutes", small: "10 journeys · 65 steps", at: 0.4 }, { big: "~$1.50", small: "AI cost for the full run", at: 2.6 }, { big: "~60% less", small: "Manual regression effort (estimate)", at: v[1] + 0.4 }, { big: "Any web app", small: "An address, a sign-in and a plan", at: v[2] + 0.4 }] } },
    ] },

    { id: "next", chapter: "Next steps", tail: 3.2, shots: [
      { from: 0, info: { title: "Next steps", cols: 3, items: [{ big: "Pilot", small: "1–2 Chryselys client apps", at: 0.5 }, { big: "Pipeline", small: "Run on every release", at: 4.2 }, { big: "Pre-sales", small: "A prototype check before every demo", at: n[1] + 0.4 }] } },
      { from: n[2] - 0.2, outro: true },
    ], noSubs: false },
  ];
}
