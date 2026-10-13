import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, fontFamily, BAND_TOP, H, FRAME } from "./theme";

export type Line = { text: string; start: number; end: number };
export const Subtitles: React.FC<{ lines: Line[]; chapter?: string }> = ({ lines, chapter }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const t = f / fps;
  const cur = lines.find((l) => t >= l.start - 0.05 && t < l.end + 0.25);
  const p = cur ? interpolate(t, [cur.start - 0.05, cur.start + 0.15, cur.end + 0.05, cur.end + 0.25], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  const cp = interpolate(t, [0.1, 0.6], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: BAND_TOP, height: H - BAND_TOP, fontFamily }}>
      {chapter && <div style={{ position: "absolute", left: FRAME.x, top: 12, opacity: cp, color: C.gold, fontSize: 19, letterSpacing: 4, fontWeight: 700 }}>{chapter.toUpperCase()}</div>}
      <div style={{ position: "absolute", left: 0, right: 0, top: 36, bottom: 0, display: "grid", placeItems: "center", opacity: p }}>
        <div style={{ color: "#fff", fontSize: 31, fontWeight: 600, letterSpacing: -0.2, textAlign: "center", maxWidth: 1600, lineHeight: 1.14, textShadow: "0 2px 12px rgba(0,0,0,.4)" }}>{cur?.text}</div>
      </div>
    </div>
  );
};
