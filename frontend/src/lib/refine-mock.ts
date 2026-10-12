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

/** Demo-mode stand-in for "create a test plan from the product document": one goal-driven journey per sentence. */
export function mockPlanFromPrd(prd: string, baseUrl: string): { markdown: string; warnings: string[]; notes: string } {
  const lines = sentences(prd).slice(0, 6);
  const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").split("-").slice(0, 5).join("-") || "journey";
  const keys = lines.map((l, i) => `${slug(l)}-${i + 1}`);
  const md = [
    "# Playbook: From the product document", `base_url: ${baseUrl}`, "",
    "## Requirements", ...lines.flatMap((l, i) => [`### REQ-${i + 1}: ${l.replace(/\.$/, "")}`, `- acceptance: ${l}`, "- priority: high", ""]),
    "## Edge cases", `### EC-1: Missing or invalid input`, `- applies_to: ${keys[0] ?? "journey"}`, "- expect: A clear error is shown and nothing is saved.", "- covers: REQ-1", "",
    "## Flows",
    ...lines.flatMap((l, i) => [`### Flow: ${keys[i]}`, `- covers: REQ-${i + 1}`, "- severity: high", "", "#### Goal", l, "", "#### Expect", `- ${l.replace(/\.$/, "")}`, ""]),
  ].join("\n");
  return { markdown: md, warnings: [], notes: "Demo mode: the real AI writes a thoughtful plan; this is a simple stand-in with one journey per sentence." };
}
