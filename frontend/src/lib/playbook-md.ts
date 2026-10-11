// Edits playbook Markdown by item, so the form cards and the raw view stay in sync (the Markdown is the source of truth).

export type Category = "requirement" | "flow" | "formula" | "ux_rule" | "gotcha" | "edge_case" | "reasoning_example";

export const CATEGORIES: { id: Category; label: string; heading: string; prefix: string; hint: string }[] = [
  { id: "requirement", label: "Requirements", heading: "Requirements", prefix: "REQ-", hint: "Testable statements from the PRD. Flows, formulas and edge cases point at them." },
  { id: "flow", label: "Flows", heading: "Flows", prefix: "", hint: "User journeys: steps, expectations, test data, and the checks they run." },
  { id: "formula", label: "Formulas", heading: "Formulas", prefix: "F-", hint: "Calculations verified in code against UI and API values." },
  { id: "ux_rule", label: "UX rules", heading: "UX rules", prefix: "UX-", hint: "Consistency and usability rules, checked by code or judged by a model." },
  { id: "gotcha", label: "Gotchas", heading: "Gotchas", prefix: "G-", hint: "Known traps in this app that would cause false findings." },
  { id: "edge_case", label: "Edge cases", heading: "Edge cases", prefix: "EC-", hint: "Unusual inputs or states; each runs as a variant of its flow." },
  { id: "reasoning_example", label: "Reasoning examples", heading: "Reasoning examples", prefix: "RX-", hint: "Few-shot guidance for Claude on tricky situations." },
];

export interface FieldSpec {
  name: string;
  label: string;
  kind: "text" | "area" | "lines" | "select" | "scope";
  options?: string[];
  hint?: string;
  placeholder?: string;
  show?: (v: Record<string, string>) => boolean;
  required?: boolean;
}

const SEV = ["low", "medium", "high", "critical"];
export const FORMS: Record<Category, FieldSpec[]> = {
  requirement: [
    { name: "title", label: "Statement", kind: "text", required: true, placeholder: "Cart total applies the discount before tax" },
    { name: "prd_ref", label: "PRD reference", kind: "text", placeholder: "§3.2 Pricing" },
    { name: "acceptance", label: "Acceptance criteria", kind: "area", required: true },
    { name: "priority", label: "Priority", kind: "select", options: SEV },
  ],
  flow: [
    { name: "title", label: "Flow key", kind: "text", required: true, placeholder: "add-to-cart", hint: "Lowercase with hyphens. Keep it stable across versions." },
    { name: "severity", label: "Severity", kind: "select", options: SEV },
    { name: "covers", label: "Covers", kind: "text", placeholder: "REQ-1, REQ-2" },
    { name: "checks", label: "Checks", kind: "text", placeholder: "F-1, UX-1" },
    { name: "steps", label: "Steps", kind: "lines", required: true, hint: "One per line. “Open /path” navigates without a model call." },
    { name: "expect", label: "Expectations", kind: "lines" },
    { name: "test_data", label: "Test data", kind: "lines", hint: "key: value, one per line" },
  ],
  formula: [
    { name: "title", label: "Name", kind: "text", required: true, placeholder: "cart_total" },
    { name: "rule", label: "Rule", kind: "area", required: true, placeholder: "total == round((subtotal - discount) * (1 + tax_rate), 2)", hint: "Evaluated in code. Allowed: sum, round, abs, min, max, len." },
    { name: "bindings", label: "Bindings", kind: "lines", required: true, hint: "var=api:/path.field, var=ui:[css selector], var=const:value; one per line" },
    { name: "tolerance", label: "Tolerance", kind: "text", placeholder: "0.01" },
    { name: "verifies", label: "Verifies", kind: "text", placeholder: "REQ-1" },
  ],
  ux_rule: [
    { name: "title", label: "Rule", kind: "text", required: true },
    { name: "check", label: "Check type", kind: "select", options: ["consistent_value", "format", "max_wait", "no_console_errors", "a11y", "judged"] },
    { name: "targets", label: "Targets", kind: "text", placeholder: "ui:[data-testid=badge], api:/api/cart.count", show: (v) => v.check === "consistent_value" || v.check === "format" },
    { name: "pattern", label: "Pattern", kind: "text", placeholder: "^\\$\\d+\\.\\d{2}$", show: (v) => v.check === "format" },
    { name: "max_ms", label: "Longest allowed wait (ms)", kind: "text", placeholder: "3000", show: (v) => v.check === "max_wait" },
    { name: "question", label: "Yes/no question", kind: "area", show: (v) => v.check === "judged" },
    { name: "severity", label: "Severity", kind: "select", options: SEV },
  ],
  gotcha: [
    { name: "title", label: "Trap", kind: "text", required: true },
    { name: "note", label: "Note", kind: "area", required: true, hint: "Shown to the planner and judge." },
    { name: "wait_for", label: "Wait for response (optional)", kind: "text", placeholder: "api:/api/cart" },
    { name: "ignore_console", label: "Ignore console errors matching (optional)", kind: "text", placeholder: "ResizeObserver" },
  ],
  edge_case: [
    { name: "title", label: "Case", kind: "text", required: true },
    { name: "applies_to", label: "Applies to flow", kind: "select", options: [] },
    { name: "expect", label: "Expected behaviour", kind: "area", required: true },
    { name: "covers", label: "Covers", kind: "text", placeholder: "REQ-3" },
    { name: "checks", label: "Checks", kind: "text", placeholder: "UX-3" },
    { name: "test_data", label: "Test data", kind: "text", placeholder: "coupon=EXPIRED10", hint: "key=value, comma separated. Use <empty> for an empty field." },
  ],
  reasoning_example: [
    { name: "title", label: "Scenario", kind: "text", required: true },
    { name: "context", label: "Context and challenge", kind: "area" },
    { name: "strategy", label: "Strategy", kind: "lines", required: true, hint: "One numbered step per line." },
    { name: "scope", label: "Used by", kind: "scope", options: ["planner", "escalation", "judge", "report"] },
  ],
};

const lines = (v: string) => v.split("\n").map((l) => l.trim()).filter(Boolean);

export function itemMarkdown(cat: Category, key: string, v: Record<string, string>): string {
  const f = (name: string) => (v[name] ?? "").trim();
  const field = (name: string, value = f(name)) => (value ? `- ${name}: ${value}\n` : "");
  switch (cat) {
    case "requirement":
      return `### ${key}: ${f("title")}\n${field("prd_ref")}${field("acceptance")}${field("priority")}`;
    case "flow": {
      let md = `### Flow: ${f("title")}\n${field("covers")}${field("checks")}${field("severity")}\n#### Steps\n${lines(v.steps ?? "").map((s, i) => `${i + 1}. ${s.replace(/^\d+[.)]\s*/, "")}`).join("\n")}\n`;
      if (f("expect")) md += `\n#### Expect\n${lines(v.expect).map((s) => `- ${s.replace(/^-\s*/, "")}`).join("\n")}\n`;
      if (f("test_data")) md += `\n#### Test data\n${lines(v.test_data).map((s) => `- ${s.replace(/^-\s*/, "")}`).join("\n")}\n`;
      return md;
    }
    case "formula":
      return `### ${key}: ${f("title")}\n- rule: \`${f("rule").replace(/`/g, "")}\`\n- bindings: ${lines(v.bindings ?? "").join(", ")}\n${field("tolerance")}${field("verifies")}`;
    case "ux_rule":
      return `### ${key}: ${f("title")}\n${field("check")}${field("targets")}${field("pattern")}${field("max_ms")}${field("question")}${field("severity")}`;
    case "gotcha":
      return `### ${key}: ${f("title")}\n${field("wait_for")}${field("ignore_console")}${field("note")}`;
    case "edge_case":
      return `### ${key}: ${f("title")}\n${field("applies_to")}${field("expect")}${field("covers")}${field("checks")}${field("test_data")}`;
    case "reasoning_example":
      return `### ${key}: ${f("title")}\n${field("scope", f("scope"))}${field("context")}- strategy:\n${lines(v.strategy ?? "").map((s, i) => `  ${i + 1}. ${s.replace(/^\d+[.)]\s*/, "")}`).join("\n")}\n`;
  }
}

/** Appends an item block to its category section, creating the section if the file has none yet. */
export function insertItem(md: string, heading: string, block: string): string {
  const ls = md.replace(/\s+$/, "").split("\n");
  const at = ls.findIndex((l) => l.trim().toLowerCase() === `## ${heading}`.toLowerCase());
  if (at < 0) return `${ls.join("\n")}\n\n## ${heading}\n${block.replace(/\s+$/, "")}\n`;
  let end = ls.length;
  for (let i = at + 1; i < ls.length; i++) if (/^##\s/.test(ls[i]) && !/^###/.test(ls[i])) { end = i; break; }
  const before = ls.slice(0, end).join("\n").replace(/\s+$/, "");
  const after = ls.slice(end).join("\n");
  return `${before}\n\n${block.replace(/\s+$/, "")}\n${after ? `\n${after}\n` : ""}`;
}

/** Removes one item (its heading through the line before the next ### or ## heading). */
export function removeItem(md: string, key: string): string {
  const ls = md.split("\n");
  const start = ls.findIndex((l) => new RegExp(`^###\\s+(${escapeRe(key)}\\s*:|Flow:\\s*${escapeRe(key)}\\s*$)`, "i").test(l));
  if (start < 0) return md;
  let end = ls.length;
  for (let i = start + 1; i < ls.length; i++) if (/^###?\s/.test(ls[i]) && !/^####/.test(ls[i])) { end = i; break; }
  return [...ls.slice(0, start), ...ls.slice(end)].join("\n").replace(/\n{3,}/g, "\n\n");
}
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function nextKey(existing: string[], prefix: string): string {
  const n = existing.filter((k) => k.startsWith(prefix)).map((k) => Number(k.slice(prefix.length))).filter(Number.isFinite);
  return `${prefix}${Math.max(0, ...n) + 1}`;
}

/** Line diff (LCS) for the normalize preview. */
export function diffLines(a: string, b: string): { type: "same" | "add" | "del"; text: string }[] {
  const x = a.split("\n"), y = b.split("\n");
  const dp = Array.from({ length: x.length + 1 }, () => new Array<number>(y.length + 1).fill(0));
  for (let i = x.length - 1; i >= 0; i--) for (let j = y.length - 1; j >= 0; j--) dp[i][j] = x[i] === y[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: { type: "same" | "add" | "del"; text: string }[] = [];
  let i = 0, j = 0;
  while (i < x.length && j < y.length) {
    if (x[i] === y[j]) { out.push({ type: "same", text: x[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ type: "del", text: x[i++] });
    else out.push({ type: "add", text: y[j++] });
  }
  while (i < x.length) out.push({ type: "del", text: x[i++] });
  while (j < y.length) out.push({ type: "add", text: y[j++] });
  return out;
}
