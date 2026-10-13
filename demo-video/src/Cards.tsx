import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, fontFamily } from "./theme";

export const Bg: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: `radial-gradient(900px 500px at 85% -10%, rgba(96,165,215,.28), transparent 70%), linear-gradient(135deg, #1a4f75 0%, ${C.navy2} 45%, ${C.navy} 100%)`, fontFamily }}>{children}</AbsoluteFill>
);
const Logo: React.FC<{ size: number }> = ({ size }) => (
  <div style={{ width: size, height: size, borderRadius: size * 0.26, background: C.gold, display: "grid", placeItems: "center", boxShadow: "0 12px 40px rgba(0,0,0,.35)" }}>
    <svg width={size * 0.58} height={size * 0.58} viewBox="0 0 24 24" fill="none" stroke="#1b1405" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
  </div>
);
const useIn = () => { const f = useCurrentFrame(); return (d: number, len = 16) => interpolate(f, [d, d + len], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); };

export const Intro: React.FC = () => {
  const f = useCurrentFrame(); const { fps, durationInFrames: D } = useVideoConfig(); const s = spring({ frame: f, fps, config: { damping: 18 } }); const a = useIn();
  const out = interpolate(f, [D - 10, D], [1, 0], { extrapolateLeft: "clamp" });
  return (
    <Bg><AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: out, gap: 22 }}>
      <div style={{ transform: `scale(${0.85 + 0.15 * s})`, opacity: s, display: "flex", alignItems: "center", gap: 30 }}><Logo size={120} /><div style={{ color: "#fff", fontSize: 120, fontWeight: 800, letterSpacing: -3 }}>QAgent</div></div>
      <div style={{ opacity: a(14), color: C.gold, fontSize: 26, letterSpacing: 5, fontWeight: 700 }}>TECHATHON 2026 · TEAM CYNACS</div>
    </AbsoluteFill></Bg>
  );
};

export const Outro: React.FC = () => {
  const a = useIn(); const up = (d: number) => 24 * (1 - a(d, 18));
  return (
    <Bg><AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 26, color: "#fff" }}>
      <div style={{ opacity: a(0), transform: `translateY(${up(0)}px)`, display: "flex", alignItems: "center", gap: 28 }}><Logo size={104} /><div style={{ fontSize: 104, fontWeight: 800, letterSpacing: -3 }}>QAgent</div></div>
      <div style={{ opacity: a(12), transform: `translateY(${up(12)}px)`, fontSize: 44, fontWeight: 500, color: "#dce8f1" }}>Test it the way your customers will use it.</div>
      <div style={{ opacity: a(28), transform: `translateY(${up(28)}px)`, display: "flex", gap: 16, marginTop: 18 }}>
        {["Plain English in", "Proof out", "Replay for free"].map((t) => <div key={t} style={{ border: "1.5px solid rgba(255,255,255,.35)", borderRadius: 999, padding: "12px 26px", fontSize: 28 }}>{t}</div>)}
      </div>
      <div style={{ opacity: a(46), position: "absolute", bottom: 70, fontSize: 24, letterSpacing: 5, color: C.gold, fontWeight: 700 }}>TECHATHON 2026 · TEAM CYNACS · CHRYSELYS</div>
    </AbsoluteFill></Bg>
  );
};

export type InfoItem = { big: string; small: string; at: number };
export const InfoCard: React.FC<{ title: string; items: InfoItem[]; cols?: number }> = ({ title, items, cols = 2 }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const t = f / fps;
  const p = (d: number) => interpolate(t, [d, d + 0.5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Bg><AbsoluteFill style={{ padding: "90px 150px", color: "#fff" }}>
      <div style={{ fontSize: 28, letterSpacing: 5, color: C.gold, fontWeight: 700, opacity: p(0) }}>{title.toUpperCase()}</div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 28, marginTop: 44 }}>
        {items.map((it, i) => (
          <div key={i} style={{ opacity: p(it.at), transform: `translateY(${(1 - p(it.at)) * 26}px)`, background: "rgba(255,255,255,.08)", border: "1.5px solid rgba(255,255,255,.18)", borderRadius: 20, padding: "34px 40px" }}>
            <div style={{ fontSize: 76, fontWeight: 800, letterSpacing: -2, color: "#fff", lineHeight: 1.05 }}>{it.big}</div>
            <div style={{ fontSize: 30, color: "#cfe0ee", marginTop: 10, fontWeight: 500 }}>{it.small}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill></Bg>
  );
};

export const BigText: React.FC<{ at: number; dur: number; text: string; sub?: string; color?: string }> = ({ at, dur, text, sub, color }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const t = f / fps;
  const p = interpolate(t, [at, at + 0.4, at + dur - 0.35, at + dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (p <= 0) return null;
  return (
    <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", opacity: p, background: `rgba(6,22,36,${0.62 * p})`, fontFamily }}>
      <div style={{ textAlign: "center", transform: `translateY(${(1 - p) * 20}px)` }}>
        <div style={{ fontSize: 112, fontWeight: 800, color: color ?? "#fff", letterSpacing: -2, textShadow: "0 6px 30px rgba(0,0,0,.5)" }}>{text}</div>
        {sub && <div style={{ fontSize: 40, color: "#e5eef6", marginTop: 10, fontWeight: 500 }}>{sub}</div>}
      </div>
    </div>
  );
};

export const SpeedTag: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ position: "absolute", right: 168, top: 40, background: "rgba(7,24,38,.78)", color: "#fff", fontFamily, fontWeight: 600, fontSize: 22, padding: "8px 18px", borderRadius: 999, border: "1.5px solid rgba(255,255,255,.35)" }}>⏩ {text}</div>
);
export const Stack: React.FC<{ items: { text: string; at: number }[] }> = ({ items }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const t = f / fps;
  return (
    <div style={{ position: "absolute", left: 134, top: 16, width: 1651, height: 929, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "flex-start", paddingLeft: 90, gap: 22, background: "rgba(7,24,38,.62)", borderRadius: 14, fontFamily }}>
      {items.map((it, i) => { const p = interpolate(t, [it.at, it.at + 0.45], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); return (
        <div key={i} style={{ opacity: p, transform: `translateX(${(1 - p) * -40}px)`, color: "#fff", fontSize: 76, fontWeight: 800, letterSpacing: -1.5, textShadow: "0 4px 24px rgba(0,0,0,.5)" }}><span style={{ color: C.gold, marginRight: 24 }}>{i + 1}</span>{it.text}</div>
      ); })}
    </div>
  );
};
