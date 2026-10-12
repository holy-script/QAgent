// Demo-mode stand-in for the AI "tidy up": simple, deterministic clean-up so the screens can be tried with no backend.
export type RefineKind = "tidy" | "description" | "prd" | "notes";

const FILLERS = /\b(?:um+|uh+|erm|you know|i mean|sort of|kind of)\b[,]?\s*/gi;

function sentences(text: string): string[] {
  const cleaned = text.replace(FILLERS, "").replace(/\s+/g, " ").trim();
  return cleaned.split(/(?<=[.!?])\s+|\n+/).map((s) => s.trim()).filter(Boolean)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1)).map((s) => (/[.!?]$/.test(s) ? s : s + "."));
}

export function mockRefine(text: string, kind: RefineKind): { text: string; notes: string | null } {
  const s = sentences(text);
  if (!s.length) return { text: "", notes: null };
  if (kind === "description") return { text: s.slice(0, 2).join(" "), notes: null };
  if (kind === "notes") return { text: s.map((x) => `- ${x}`).join("\n"), notes: null };
  if (kind === "prd") {
    return {
      text: ["# Product", "", "## Overview", s[0], "", "## Features and requirements", ...s.slice(1).map((x, i) => `${i + 1}. ${x}`), "", "## Open questions", "- Anything above that sounds unclear."].join("\n"),
      notes: "Demo mode: the real AI organises this into sections; this is a simple stand-in.",
    };
  }
  return { text: s.join(" "), notes: null };
}
