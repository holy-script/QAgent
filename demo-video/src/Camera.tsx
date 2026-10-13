import React from "react";
import { Easing, interpolate, Video, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { FRAME } from "./theme";
import { TRACKS } from "./tracks";

type Row = number[]; // [t, x, y, w, h] in source (CSS) pixels
export type Key = { t: number; x?: number; y?: number; s?: number; follow?: string; fit?: string; pad?: number };
export type Callout = { track: string; at?: number; dur?: number; label?: string; color?: string; pad?: number; spot?: boolean; side?: "below" | "above" };
export type ClipSpec = { src: string; start: number; rate: number; keys: Key[]; callouts?: Callout[] };

const ease = Easing.bezier(0.45, 0, 0.2, 1);
const clipId = (src: string) => src.replace(/\.mp4$/, "");

function boxAt(clip: string, name: string, t: number): number[] | null {
  const rows: Row[] | undefined = (TRACKS as any)[clip]?.[name];
  if (!rows || !rows.length || t < rows[0][0]) return null;
  let lo = 0, hi = rows.length - 1;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (rows[m][0] <= t) lo = m; else hi = m - 1; }
  const a = rows[lo]; if (a[3] === 0) return null;
  const b = rows[lo + 1];
  if (b && b[3] > 0 && b[0] - a[0] < 0.2) { const p = (t - a[0]) / (b[0] - a[0]); return [1, 2, 3, 4].map((i) => a[i] + (b[i] - a[i]) * p); }
  return [a[1], a[2], a[3], a[4]];
}
function smoothBox(clip: string, name: string, t: number) {
  const bs = [-0.2, -0.1, 0, 0.1, 0.2].map((d) => boxAt(clip, name, t + d)).filter(Boolean) as number[][];
  if (!bs.length) return null; return [0, 1, 2, 3].map((i) => bs.reduce((s, b) => s + b[i], 0) / bs.length);
}

function resolve(k: Key, clip: string, srcT: number, prev: { x: number; y: number; s: number }) {
  let x = k.x ?? prev.x, y = k.y ?? prev.y, s = k.s ?? prev.s;
  const name = k.follow ?? k.fit;
  if (name) {
    const b = smoothBox(clip, name, srcT);
    if (b) {
      x = b[0] + b[2] / 2; y = b[1] + b[3] / 2;
      if (k.fit) { const pad = k.pad ?? 60; s = Math.max(1, Math.min(2.8, Math.min(1920 / (b[2] + 2 * pad), 1080 / (b[3] + 2 * pad)))); }
    }
  }
  return { x, y, s };
}

export const ScreenClip: React.FC<{ clip: ClipSpec }> = ({ clip }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = frame / fps, id = clipId(clip.src), srcT = clip.start + t * clip.rate;
  // camera: ease between key poses, each resolved against the live (tracked) position of its target
  const keys = clip.keys; let pose = { x: 960, y: 540, s: 1 };
  const poses: { t: number; x: number; y: number; s: number }[] = [];
  keys.forEach((k, i) => { const kt = clip.start + k.t * clip.rate; const r = resolve(k, id, k.follow || k.fit ? srcT : kt, poses[i - 1] ?? pose); poses.push({ t: k.t, ...r }); });
  let cur = poses[0];
  if (t > poses[0].t) { cur = poses[poses.length - 1]; for (let i = 0; i < poses.length - 1; i++) { const a = poses[i], b = poses[i + 1]; if (t >= a.t && t <= b.t) { const p = ease((t - a.t) / (b.t - a.t || 1)); cur = { t, x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p, s: a.s + (b.s - a.s) * p }; break; } } }
  const k = FRAME.scale * cur.s;
  const tx = Math.min(0, Math.max(FRAME.w - 1920 * k, FRAME.w / 2 - cur.x * k));
  const ty = Math.min(0, Math.max(FRAME.h - 1080 * k, FRAME.h / 2 - cur.y * k));
  const vis = { x0: -tx / k, y0: -ty / k, x1: (FRAME.w - tx) / k, y1: (FRAME.h - ty) / k };
  return (
    <div style={{ position: "absolute", left: FRAME.x, top: FRAME.y, width: FRAME.w, height: FRAME.h, borderRadius: FRAME.r, overflow: "hidden", boxShadow: "0 30px 80px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.1)", background: "#fff" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${k})` }}>
        <Video src={staticFile(`footage/${clip.src}`)} startFrom={Math.round(clip.start * fps)} playbackRate={clip.rate} muted style={{ width: 1920, height: 1080 }} />
        {(clip.callouts ?? []).map((co, i) => <CalloutBox key={i} co={co} clip={id} t={t} srcT={srcT} k={k} vis={vis} />)}
      </div>
    </div>
  );
};

const CalloutBox: React.FC<{ co: Callout; clip: string; t: number; srcT: number; k: number; vis: { x0: number; y0: number; x1: number; y1: number } }> = ({ co, clip, t, srcT, k, vis }) => {
  const at = co.at ?? 0, dur = co.dur ?? 999;
  const p = interpolate(t, [at, at + 0.35, at + dur - 0.3, at + dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (p <= 0) return null;
  const b = boxAt(clip, co.track, srcT); if (!b) return null;
  const pad = co.pad ?? 8, col = co.color ?? "#e0a93a";
  const x = b[0] - pad, y = b[1] - pad, w = b[2] + 2 * pad, h = b[3] + 2 * pad;
  const lw = 3.5 / k, fs = 25 / k, gap = 12 / k, lh = fs * 1.9;
  const lwid = (co.label?.length ?? 0) * fs * 0.58 + fs * 1.4;
  let lx = Math.min(Math.max(x, vis.x0 + 10 / k), vis.x1 - lwid - 10 / k);
  const below = (co.side ?? "below") === "below";
  let ly = below ? y + h + gap : y - gap - lh;
  if (ly + lh > vis.y1 - 8 / k) ly = y - gap - lh; if (ly < vis.y0 + 8 / k) ly = y + h + gap;
  ly = Math.min(Math.max(ly, vis.y0 + 8 / k), vis.y1 - lh - 8 / k);
  return (
    <>
      <div style={{ position: "absolute", left: x, top: y, width: w, height: h, opacity: p, borderRadius: 10 / k, border: `${lw}px solid ${col}`, boxShadow: co.spot ? `0 0 0 4000px rgba(7,24,38,${0.5 * p})` : `0 0 0 ${1 / k}px rgba(0,0,0,.25)`, transform: `scale(${0.985 + 0.015 * p})` }} />
      {co.label && <div style={{ position: "absolute", left: lx, top: ly, height: lh, padding: `0 ${fs * 0.7}px`, display: "flex", alignItems: "center", opacity: p, background: col, color: col === "#e0a93a" ? "#1b1405" : "#fff", fontWeight: 700, fontSize: fs, borderRadius: 8 / k, whiteSpace: "nowrap", boxShadow: `0 ${4 / k}px ${14 / k}px rgba(0,0,0,.3)` }}>{co.label}</div>}
    </>
  );
};
