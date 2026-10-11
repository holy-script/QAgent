// Edits playbook Markdown by item, so the form cards and the raw view stay in sync (the Markdown is the source of truth).

export type Category = "requirement" | "flow" | "formula" | "ux_rule" | "gotcha" | "edge_case" | "reasoning_example";

export const CATEGORIES: { id: Category; label: string; heading: string; prefix: string; hint: string }[] = [
  { id: "requirement", label: "Requirements", heading: "Requirements", prefix: "REQ-", hint: "Things the product must do, taken from your product document. Journeys and checks point at them so you can see what is proven." },
  { id: "flow", label: "Journeys", heading: "Flows", prefix: "", hint: "A path a user takes, such as adding an item and opening the cart: its steps, what should be true afterwards, and the checks it runs." },
  { id: "formula", label: "Calculations", heading: "Formulas", prefix: "F-", hint: "Math the app must get right, such as a cart total. QAgent recomputes it itself and compares with what the page shows." },
  { id: "ux_rule", label: "Usability rules", heading: "UX rules", prefix: "UX-", hint: "Things that should look or behave consistently, such as the cart count matching, or nothing loading for longer than a few seconds." },
  { id: "gotcha", label: "Known quirks", heading: "Gotchas", prefix: "G-", hint: "Things about your app that could fool the test, such as a count that updates a moment late. Telling QAgent avoids false alarms." },
  { id: "edge_case", label: "Unusual cases", heading: "Edge cases", prefix: "EC-", hint: "Odd situations worth trying, such as an expired coupon or a missing postal code. Each one re-runs its journey with different data." },
  { id: "reasoning_example", label: "Examples for the AI", heading: "Reasoning examples", prefix: "RX-", hint: "Worked examples that teach the stronger AI how to handle a tricky situation. Optional." },
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
    { name: "title", label: "Journey name", kind: "text", required: true, placeholder: "add-to-cart", hint: "Lowercase with hyphens. Keep it the same across versions so history stays together." },
    { name: "severity", label: "Severity", kind: "select", options: SEV },
    { name: "covers", label: "Requirements it proves", kind: "text", placeholder: "REQ-1, REQ-2" },
    { name: "checks", label: "Calculations and rules to check", kind: "text", placeholder: "F-1, UX-1" },
    { name: "steps", label: "Steps", kind: "lines", required: true, hint: "One per line, in plain words, e.g. “Add 2 items to cart”. “Open /products” opens a page directly." },
    { name: "expect", label: "What should be true afterwards", kind: "lines" },
    { name: "test_data", label: "Values to type in", kind: "lines", hint: "name: value, one per line, e.g. coupon: SAVE10" },
  ],
  formula: [
    { name: "title", label: "Name", kind: "text", required: true, placeholder: "cart_total" },
    { name: "rule", label: "The calculation", kind: "area", required: true, placeholder: "total == round((subtotal - discount) * (1 + tax_rate), 2)", hint: "Written like a formula using the names below. QAgent checks it with code, not AI." },
    { name: "bindings", label: "Where each value comes from", kind: "lines", required: true, hint: "One per line: name=api:/path.field (from the server), name=ui:[css selector] (read off the page), or name=const:value (a fixed number)" },
    { name: "tolerance", label: "Tolerance", kind: "text", placeholder: "0.01" },
    { name: "verifies", label: "Requirement it proves", kind: "text", placeholder: "REQ-1" },
  ],
  ux_rule: [
    { name: "title", label: "Rule", kind: "text", required: true },
    { name: "check", label: "Kind of rule", kind: "select", options: ["consistent_value", "format", "max_wait", "no_console_errors", "a11y", "judged"] },
    { name: "targets", label: "Targets", kind: "text", placeholder: "ui:[data-testid=badge], api:/api/cart.count", show: (v) => v.check === "consistent_value" || v.check === "format" },
    { name: "pattern", label: "Pattern", kind: "text", placeholder: "^\\$\\d+\\.\\d{2}$", show: (v) => v.check === "format" },
    { name: "max_ms", label: "Longest allowed wait (ms)", kind: "text", placeholder: "3000", show: (v) => v.check === "max_wait" },
    { name: "question", label: "Yes/no question", kind: "area", show: (v) => v.check === "judged" },
    { name: "severity", label: "Severity", kind: "select", options: SEV },
  ],
  gotcha: [
    { name: "title", label: "Trap", kind: "text", required: true },
    { name: "note", label: "Note", kind: "area", required: true, hint: "Shown to the planner and judge." },
    { name: "wait_for", label: "Wait for this server call first (optional)", kind: "text", placeholder: "api:/api/cart" },
    { name: "ignore_console", label: "Ignore browser errors containing (optional)", kind: "text", placeholder: "ResizeObserver" },
  ],
  edge_case: [
    { name: "title", label: "Case", kind: "text", required: true },
    { name: "applies_to", label: "Which journey", kind: "select", options: [] },
    { name: "expect", label: "What should happen", kind: "area", required: true },
    { name: "covers", label: "Covers", kind: "text", placeholder: "REQ-3" },
    { name: "checks", label: "Checks", kind: "text", placeholder: "UX-3" },
    { name: "test_data", label: "Values to use", kind: "text", placeholder: "coupon=EXPIRED10", hint: "name=value, comma separated. Use <empty> to leave a field blank." },
  ],
  reasoning_example: [
    { name: "title", label: "Scenario", kind: "text", required: true },
    { name: "context", label: "Context and challenge", kind: "area" },
    { name: "strategy", label: "How to handle it", kind: "lines", required: true, hint: "One step per line." },
    { name: "scope", label: "Where the AI uses it", kind: "scope", options: ["planner", "escalation", "judge", "report"] },
  ],
};

const lines = (v: string) => v.split("\n").map((l) => l.trim()).filter(Boolean);

export function itemMarkdown(cat: Category, key: string, v: Record<string, string>, extra = ""): string {
  const out = itemBlock(cat, key, v);
  return extra ? `${out.replace(/\s+$/, "")}\n${extra}` : out;
}

function itemBlock(cat: Category, key: string, v: Record<string, string>): string {
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

/** Replaces one item's block in place (same position in the file). */
export function replaceItem(md: string, key: string, block: string): string {
  const ls = md.split("\n");
  const start = ls.findIndex((l) => new RegExp(`^###\\s+(${escapeRe(key)}\\s*:|Flow:\\s*${escapeRe(key)}\\s*$)`, "i").test(l));
  if (start < 0) return md;
  let end = ls.length;
  for (let i = start + 1; i < ls.length; i++) if (/^###?\s/.test(ls[i]) && !/^####/.test(ls[i])) { end = i; break; }
  const tail = ls.slice(end);
  return [...ls.slice(0, start), ...block.replace(/\s+$/, "").split("\n"), ...(tail.length ? ["", ...tail] : [])].join("\n");
}

const join = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v ? String(v) : "");
const pairs = (v: unknown, sep: string) => (v && typeof v === "object" ? Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k}${sep}${x}`) : []);

/** The form values that would regenerate an existing parsed item (the reverse of itemMarkdown). */
export function itemToValues(cat: Category, item: { key: string; title: string; body: Record<string, unknown> }): Record<string, string> {
  const b = item.body;
  const str = (k: string) => (b[k] == null ? "" : String(b[k]));
  switch (cat) {
    case "requirement": return { title: item.title, prd_ref: str("prd_ref"), acceptance: str("acceptance"), priority: str("priority") || "high" };
    case "flow": return { title: item.key, severity: str("severity") || "high", covers: join(b.covers), checks: join(b.checks), steps: ((b.steps as string[]) ?? []).join("\n"), expect: ((b.expect as string[]) ?? []).join("\n"), test_data: pairs(b.test_data, ": ").join("\n") };
    case "formula": return { title: item.title, rule: str("rule"), bindings: pairs(b.bindings, "=").join("\n"), tolerance: str("tolerance"), verifies: join(b.verifies) };
    case "ux_rule": return { title: item.title, check: str("check"), targets: join(b.targets), pattern: str("pattern"), max_ms: str("max_ms"), question: str("question"), severity: str("severity") || "medium" };
    case "gotcha": return { title: item.title, note: str("note"), wait_for: str("wait_for"), ignore_console: str("ignore_console") };
    case "edge_case": return { title: item.title, applies_to: str("applies_to"), expect: str("expect"), covers: join(b.covers), checks: join(b.checks), test_data: pairs(b.test_data, "=").join(", ") };
    case "reasoning_example": return { title: item.title, context: str("context"), strategy: ((b.strategy as string[]) ?? []).join("\n"), scope: join(b.scope) };
  }
}

const FLOW_BLOCKS = new Set(["steps", "expect", "test_data"]);
/** `- field: value` lines for fields an item has that the form does not show, so editing never drops them. */
export function extraFieldLines(cat: Category, body: Record<string, unknown>): string {
  const shown = new Set(FORMS[cat].map((f) => f.name));
  return Object.entries(body)
    .filter(([k, v]) => !shown.has(k) && !FLOW_BLOCKS.has(k) && v != null && !(Array.isArray(v) && !v.length))
    .map(([k, v]) => `- ${k}: ${Array.isArray(v) ? v.join(", ") : typeof v === "object" ? Object.entries(v as object).map(([a, b]) => `${a}=${b}`).join(", ") : v}`)
    .join("\n");
}
