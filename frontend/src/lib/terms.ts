// One place for the words the UI uses, so every page says the same thing. The backend keeps its own names
// (playbook, flow, finding, ...); this file is the translation to plain language.
import type { Mode } from "@/lib/api/types";

export const MODE_INFO: Record<Mode, { label: string; short: string; hint: string }> = {
  hybrid: { label: "Smart", short: "Smart", hint: "A fast AI picks each action; a stronger AI double-checks when the fast one is unsure. Best balance of speed and cost." },
  baseline: { label: "Thorough", short: "Thorough", hint: "The stronger AI makes every decision. Slower and costs more, useful as a comparison." },
  stub: { label: "Practice", short: "Practice", hint: "No AI: follows simple rules. Free and fast, good for checking your setup works." },
};

export const ISSUE_STATUS: Record<string, { label: string; hint: string }> = {
  open: { label: "Open", hint: "Found in the latest run and not fixed yet." },
  regressed: { label: "Came back", hint: "Was fixed earlier, but a newer run found it again." },
  resolved: { label: "Fixed", hint: "A later run exercised the same journey and no longer found it." },
};

export const FINDING_KIND: Record<string, string> = { formula: "Calculation", dom: "On screen", network: "Server", timing: "Speed" };

export const CATEGORY_LABEL: Record<string, string> = {
  requirement: "Requirements", flow: "Journeys", formula: "Calculations", ux_rule: "Usability rules",
  gotcha: "Known quirks", edge_case: "Unusual cases", reasoning_example: "Examples for the AI",
};

export const GLOSSARY: { term: string; meaning: string }[] = [
  { term: "App", meaning: "A website or web app you want to test, identified by its address (URL)." },
  { term: "Test plan", meaning: "A text file that describes what to test: the journeys to walk through, what should be true afterwards, and rules to check. Also called a playbook in the files." },
  { term: "Journey", meaning: "One path a real user would take, such as adding an item to the cart and opening the cart. A test plan has several journeys." },
  { term: "Run", meaning: "One execution of a test plan. QAgent opens a real browser, walks each journey, and records everything." },
  { term: "Mode", meaning: "How decisions are made during a run: Smart (fast AI, stronger AI when unsure), Thorough (stronger AI every time) or Practice (no AI)." },
  { term: "Fast AI / Strong AI", meaning: "The fast AI (Jev) picks the next click in a fraction of a second. The strong AI (Claude) is slower but is asked when the fast one is unsure, and writes the reports." },
  { term: "Confidence", meaning: "How sure the AI is about its choice. Below a threshold the stronger AI double-checks; far below, the step stops instead of guessing." },
  { term: "Problem found", meaning: "A check that failed during one run, such as a wrong total or a server error." },
  { term: "Bug", meaning: "The underlying defect, tracked across runs. The same problem found in several runs is one bug. It is Open, Fixed (a later run no longer finds it) or Came back." },
  { term: "Requirement", meaning: "Something the product must do, taken from your product document. Journeys and checks are linked to the requirements they prove." },
  { term: "Proof", meaning: "Everything that backs a problem: screenshots before and after, the exact server calls, the values compared, and the AI decisions that led there." },
  { term: "Repeat exactly", meaning: "Run again using the AI answers recorded last time, so the browser does the same things. Useful to check that a fix works." },
];
