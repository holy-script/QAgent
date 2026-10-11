// A TypeScript port of the backend's playbook parser and validator (backend/qagent/playbooks). It powers the editor and
// every playbook screen in demo mode, and the unit tests check it against the same cases as the backend's.
import type { ParsedFlow, Severity } from "@/lib/api/types";

export interface ParsedItem { key: string; category: string; title: string; body: Record<string, unknown> }
export interface Validation {
  title: string; base_url: string; counts: Record<string, number>; errors: string[]; warnings: string[];
  coverage: { covered_by: Record<string, string[]>; uncovered: string[] }; flows: Record<string, unknown>[];
  items: ParsedItem[]; links: { from_key: string; to_key: string; relation: string }[];
}

const SECTIONS: Record<string, string> = { requirements: "requirement", flows: "flow", formulas: "formula", "ux rules": "ux_rule", gotchas: "gotcha", "edge cases": "edge_case", "reasoning examples": "reasoning_example" };
const SECTION_KEY: Record<string, string> = { requirement: "requirements", flow: "flows", formula: "formulas", ux_rule: "ux_rules", gotcha: "gotchas", edge_case: "edge_cases", reasoning_example: "reasoning_examples" };
const PREFIX: Record<string, string> = { requirement: "REQ-", formula: "F-", ux_rule: "UX-", gotcha: "G-", edge_case: "EC-", reasoning_example: "RX-" };
const LISTS = new Set(["covers", "checks", "verifies", "scope", "targets"]);
const UX_TYPES = new Set(["consistent_value", "format", "max_wait", "no_console_errors", "a11y", "judged"]);
const FUNCS = new Set(["sum", "round", "abs", "min", "max", "len", "for", "in", "if", "else", "and", "or", "not", "True", "False"]);
const KNOWN: Record<string, string[]> = {
  requirement: ["prd_ref", "acceptance", "priority"], formula: ["rule", "source", "bindings", "tolerance", "verifies"],
  ux_rule: ["check", "targets", "pattern", "max_ms", "question", "severity", "covers", "ignore", "impact"],
  gotcha: ["note", "wait_for", "ignore_console", "applies_to"], edge_case: ["applies_to", "expect", "covers", "checks", "test_data"],
  flow: ["covers", "checks", "severity", "steps", "expect", "test_data"], reasoning_example: ["scope", "context", "challenge", "strategy"],
};

const split = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
const pairs = (v: string) => Object.fromEntries(v.split(/,\s*(?=[A-Za-z_]\w*\s*=)/).map((p) => { const i = p.indexOf("="); return i < 0 ? [p] : [p.slice(0, i), p.slice(i + 1)]; }).filter((p) => p[0]?.trim() && p[1]?.trim()).map((p) => [p[0].trim(), p[1].trim()]));

function fields(lines: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].trimEnd().match(/^-\s+([A-Za-z_]\w*)\s*:\s*(.*)$/);
    if (!m) continue;
    const [, key, value] = m;
    if (key === "strategy") {
      const block: string[] = value ? [value] : [];
      while (i + 1 < lines.length && (/^\s/.test(lines[i + 1]) || !lines[i + 1].trim())) { const t = lines[++i].replace(/^\s*(\d+[.)]|[-*])\s*/, "").trim(); if (t) block.push(t); }
      out[key] = block;
    } else if (key === "bindings" || key === "test_data") out[key] = pairs(value);
    else if (LISTS.has(key)) out[key] = split(value);
    else if (key === "rule") out[key] = value.trim().replace(/^`|`$/g, "");
    else out[key] = key === "pattern" || key === "check" ? value.replace(/^`|`$/g, "") : value;
  }
  return out;
}

function flowBody(lines: string[]): Record<string, unknown> {
  const flow: Record<string, unknown> = { steps: [] as string[], expect: [] as string[], test_data: {} as Record<string, string> };
  const head: string[] = [];
  let section: string | null = null;
  for (const line of lines) {
    const s = line.trim();
    if (s.startsWith("####")) { section = s.replace(/^#+/, "").trim().toLowerCase(); continue; }
    if (section === null) head.push(line);
    else if (section === "steps") { const m = s.match(/^\d+[.)]\s*(.+)$/); if (m) (flow.steps as string[]).push(m[1].trim()); }
    else if (section === "expect" && s.startsWith("- ")) (flow.expect as string[]).push(s.slice(2).trim());
    else if (section === "test data" && s.startsWith("- ")) { const [k, ...v] = s.slice(2).split(":"); if (k.trim() && v.join(":").trim()) (flow.test_data as Record<string, string>)[k.trim()] = v.join(":").trim(); }
  }
  return { ...flow, ...fields(head) };
}

export function validateMarkdown(md: string, previous?: { flows: Record<string, unknown>[] }): Validation {
  const lines = md.split("\n");
  const title = lines.find((l) => l.trim().startsWith("# Playbook:"))?.replace("# Playbook:", "").trim() ?? "Playbook";
  const base_url = lines.find((l) => l.trim().startsWith("base_url:"))?.split(":").slice(1).join(":").trim() ?? "http://localhost:8001";
  const headings = lines.flatMap((l, i) => { const m = l.match(/^(#{2,3})\s+(.*)$/); return m ? [{ level: m[1].length, text: m[2].trim(), line: i }] : []; });

  const items: ParsedItem[] = [];
  const errors: string[] = [], warnings: string[] = [];
  const unknownSections: string[] = [];
  let category: string | null = null;
  headings.forEach((h, idx) => {
    if (h.level === 2) { category = SECTIONS[h.text.toLowerCase()] ?? null; if (!category) unknownSections.push(h.text); return; }
    if (!category) return;
    const next = headings.slice(idx + 1).find((x) => x.level <= 3);
    const body = lines.slice(h.line + 1, next ? next.line : lines.length);
    if (category === "flow") {
      const m = h.text.match(/^Flow\s*:\s*(.+)$/i);
      if (!m) { errors.push(`flow heading must be 'Flow: <key>', got '${h.text}'`); return; }
      items.push({ key: m[1].trim(), category, title: m[1].trim(), body: { severity: "high", covers: [], checks: [], ...flowBody(body) } });
    } else {
      const m = h.text.match(/^([A-Z]{1,3}-\d+)\s*:\s*(.*)$/);
      if (!m || !m[1].startsWith(PREFIX[category])) { errors.push(`heading '${h.text}' in '${category}' needs an ID like ${PREFIX[category]}1: Title`); return; }
      items.push({ key: m[1], category, title: m[2].trim(), body: fields(body) });
    }
  });

  const of = (c: string) => items.filter((i) => i.category === c);
  const arr = (i: ParsedItem, k: string) => ((i.body[k] as string[]) ?? []);
  const str = (i: ParsedItem, k: string) => String(i.body[k] ?? "");

  const links: Validation["links"] = [];
  const link = (from: string, to: string | string[], relation: string) => (Array.isArray(to) ? to : [to]).filter(Boolean).forEach((t) => links.push({ from_key: from, to_key: t, relation }));
  of("formula").forEach((i) => link(i.key, arr(i, "verifies"), "verifies"));
  of("flow").forEach((i) => { link(i.key, arr(i, "covers"), "covers"); link(i.key, arr(i, "checks"), "checks"); });
  of("edge_case").forEach((i) => { link(i.key, arr(i, "covers"), "covers"); link(i.key, arr(i, "checks"), "checks"); link(i.key, str(i, "applies_to"), "applies_to"); });
  of("ux_rule").forEach((i) => link(i.key, arr(i, "covers"), "covers"));
  of("gotcha").forEach((i) => link(i.key, str(i, "applies_to"), "applies_to"));

  const counts: Record<string, number> = {};
  items.forEach((i) => { counts[i.key] = (counts[i.key] ?? 0) + 1; });
  Object.entries(counts).filter(([, n]) => n > 1).forEach(([k, n]) => errors.push(`${k}: ID is defined ${n} times`));
  const keys = new Set(items.map((i) => i.key)), flowKeys = new Set(of("flow").map((i) => i.key));
  links.forEach((l) => { if (!(l.relation === "applies_to" ? flowKeys : keys).has(l.to_key)) errors.push(`${l.from_key}: ${l.relation} '${l.to_key}' does not exist`); });

  of("formula").forEach((f) => {
    const rule = str(f, "rule");
    if (!rule) { errors.push(`${f.key}: formula has no rule`); return; }
    const local = new Set([...rule.matchAll(/\bfor\s+(\w+)\s+in\b/g)].map((m) => m[1]));
    const bound = new Set(Object.keys((f.body.bindings as object) ?? {}));
    [...new Set(rule.replace(/\.\w+/g, "").match(/[A-Za-z_]\w*/g) ?? [])].filter((n) => !FUNCS.has(n) && !local.has(n) && !bound.has(n)).forEach((n) => errors.push(`${f.key}: variable '${n}' has no binding`));
    const bad = [...rule.matchAll(/\b([A-Za-z_]\w*)\s*\(/g)].map((m) => m[1]).find((n) => !FUNCS.has(n));
    if (bad) errors.push(`${f.key}: only [${[...FUNCS].filter((x) => ["sum", "round", "abs", "min", "max", "len"].includes(x)).join(", ")}] may be called`);
    Object.entries((f.body.bindings as Record<string, string>) ?? {}).forEach(([v, s]) => { if (!/^(api|ui|const):/.test(s)) errors.push(`${f.key}: binding '${v}=${s}' must start with api:, ui: or const:`); });
  });
  of("ux_rule").forEach((u) => {
    const check = str(u, "check");
    if (!UX_TYPES.has(check)) { errors.push(`${u.key}: unknown check type '${check}' (use one of ${[...UX_TYPES].sort().join(", ")})`); return; }
    const need: Record<string, string[]> = { consistent_value: ["targets"], format: ["targets", "pattern"], max_wait: ["max_ms"], judged: ["question"] };
    (need[check] ?? []).filter((f) => !u.body[f] || (Array.isArray(u.body[f]) && !(u.body[f] as unknown[]).length)).forEach((f) => errors.push(`${u.key}: check '${check}' needs field '${f}'`));
    if (check === "consistent_value" && arr(u, "targets").length < 2) errors.push(`${u.key}: consistent_value needs at least two targets`);
    if (check === "format" && str(u, "pattern")) { try { new RegExp(str(u, "pattern")); } catch { errors.push(`${u.key}: pattern does not compile`); } }
  });
  of("flow").forEach((f) => { if (!arr(f, "steps").length) errors.push(`flow ${f.key}: has no steps`); });
  of("edge_case").forEach((e) => { if (!str(e, "expect")) errors.push(`${e.key}: edge case needs an 'expect' line`); });
  of("requirement").forEach((r) => { if (!str(r, "acceptance")) warnings.push(`${r.key}: requirement has no acceptance criteria`); });

  items.forEach((i) => {
    const extra = Object.keys(i.body).filter((k) => !(KNOWN[i.category] ?? []).includes(k));
    extra.forEach((k) => warnings.push(`${i.key}: unknown field '${k}'`));
  });
  unknownSections.forEach((s) => warnings.push(`unknown section '${s}'`));

  const covered_by: Record<string, string[]> = Object.fromEntries(of("requirement").map((r) => [r.key, [] as string[]]));
  const add = (r: string, k: string) => { if (covered_by[r] && !covered_by[r].includes(k)) covered_by[r].push(k); };
  of("formula").forEach((f) => arr(f, "verifies").forEach((r) => add(r, f.key)));
  of("flow").forEach((f) => arr(f, "covers").forEach((r) => add(r, f.key)));
  of("edge_case").forEach((e) => arr(e, "covers").forEach((r) => add(r, e.key)));
  of("ux_rule").forEach((u) => arr(u, "covers").forEach((r) => add(r, u.key)));
  const uncovered = Object.entries(covered_by).filter(([, v]) => !v.length).map(([k]) => k);
  uncovered.forEach((r) => warnings.push(`${r}: requirement is not covered by any flow, formula or edge case`));

  if (previous) {
    const old = new Set(previous.flows.map((f) => String(f.key)));
    const gone = [...old].filter((k) => !flowKeys.has(k)), fresh = [...flowKeys].filter((k) => !old.has(k));
    if (gone.length && fresh.length) warnings.push(`flow renamed? [${gone.join(", ")}] -> [${fresh.join(", ")}]; its history will split`);
  }

  const secCounts = Object.fromEntries(Object.entries(SECTION_KEY).map(([cat, key]) => [key, of(cat).length]));
  return {
    title, base_url, counts: secCounts, errors, warnings, coverage: { covered_by, uncovered },
    flows: of("flow").map((f) => ({ key: f.key, ...f.body })), items, links,
  };
}

/** Flow cards for the review page (same mapping the real adapter uses). */
export function toParsedFlows(v: Validation): ParsedFlow[] {
  const formulas = v.items.filter((i) => i.category === "formula");
  const ecs = v.items.filter((i) => i.category === "edge_case");
  return v.flows.map((f) => {
    const flow = f as Record<string, unknown> & { key: string };
    return {
      key: flow.key, severity: (flow.severity as Severity) ?? "high", steps: (flow.steps as string[]) ?? [], expect: (flow.expect as string[]) ?? [],
      test_data: Object.fromEntries(Object.entries((flow.test_data as Record<string, string>) ?? {})),
      formulas: ((flow.checks as string[]) ?? []).flatMap((k) => formulas.filter((x) => x.key === k)).map((x) => ({
        name: `${x.key} ${x.title}`.trim(), expr: String(x.body.rule ?? ""), source: "both" as const, bindings: (x.body.bindings as Record<string, string>) ?? {},
      })),
      edge_cases: ecs.filter((e) => e.body.applies_to === flow.key).map((e) => `${e.key}: ${e.title}`),
    };
  });
}
