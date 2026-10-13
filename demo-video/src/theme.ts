import { loadFont } from "@remotion/google-fonts/Inter";
export const { fontFamily } = loadFont("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin"] });
export const C = { navy: "#0a2236", navy2: "#0d3250", blue: "#1a4f72", gold: "#e0a93a", white: "#ffffff", red: "#ff6b5e", green: "#4cc38a" };
export const W = 1920, H = 1080, FPS = 30;
// The screen sits in a rounded frame; a caption band below carries the chapter chip and the subtitles.
export const FRAME = { scale: 0.86, w: 1920 * 0.86, h: 1080 * 0.86, x: (1920 - 1920 * 0.86) / 2, y: 16, r: 14 };
export const BAND_TOP = FRAME.y + FRAME.h;
