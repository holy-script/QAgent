import type { ParsedFlow, ParsedFormula, PlaybookVersion, PlaybookWarning, Severity } from "./api/types";

// Mock-mode stand-in for the backend parser (B3). Same Markdown grammar as playbooks/checkout-flow.md.
const SEVERITIES = ["low", "medium", "high", "critical"];

export function parsePlaybook(md: string): Pick<PlaybookVersion, "parsed" | "warnings"> {
  const warnings: PlaybookWarning[] = [];
  const lines = md.split("\n");
  const title = lines.find((l) => l.startsWith("# "))?.replace(/^#\s*(Playbook:)?\s*/i, "").trim() ?? "";
  if (!title) warnings.push({ line: 1, level: "error", message: "Missing '# Playbook: <name>' title" });
  const baseLine = lines.findIndex((l) => /^base_url:/i.test(l));
  const base_url = baseLine >= 0 ? lines[baseLine].split(/:(.+)/)[1].trim() : null;
  if (!base_url) warnings.push({ line: 2, level: "warning", message: "No base_url; the app's base URL will be used" });

  const flows: ParsedFlow[] = [];
  let flow: ParsedFlow | null = null;
  let flowLine = 0;
  let section = "";
  let formula: ParsedFormula | null = null;
  const closeFlow = () => {
    if (!flow) return;
    if (!flow.steps.length) warnings.push({ line: flowLine, level: "error", message: `Flow '${flow.key}' has no Steps` });
    if (!flow.expect.length) warnings.push({ line: flowLine, level: "warning", message: `Flow '${flow.key}' has no Expect section; nothing will be verified` });
    flows.push(flow);
  };

  lines.forEach((raw, i) => {
    const n = i + 1;
    const line = raw.trimEnd();
    const fm = line.match(/^##\s+Flow:\s*(.+)$/i);
    if (fm) { closeFlow(); flowLine = n; section = ""; formula = null;
      flow = { key: fm[1].trim(), severity: "medium", steps: [], expect: [], test_data: {}, formulas: [], edge_cases: [] }; return; }
    if (!flow) return;
    const sm = line.match(/^###\s+(.+)$/);
    if (sm) { section = sm[1].trim().toLowerCase(); formula = null; return; }
    const sev = line.match(/^Severity:\s*(\w+)/i);
    if (sev) {
      if (SEVERITIES.includes(sev[1].toLowerCase())) flow.severity = sev[1].toLowerCase() as Severity;
      else warnings.push({ line: n, level: "error", message: `Unknown severity '${sev[1]}' (use ${SEVERITIES.join("/")})` });
      return;
    }
    if (!line.trim()) return;
    const item = line.replace(/^\s*(\d+\.|-)\s*/, "").trim();
    if (section === "steps") flow.steps.push(item);
    else if (section === "expect") flow.expect.push(item);
    else if (section === "edge cases") flow.edge_cases.push(item);
    else if (section === "test data") { const [k, ...v] = item.split(":"); flow.test_data[k.trim()] = v.join(":").trim(); }
    else if (section === "formulas") {
      if (/^\s{2,}-/.test(line) && formula) {
        const [k, ...v] = item.split(":"); const val = v.join(":").trim();
        if (k === "source") formula.source = val as ParsedFormula["source"];
        if (k === "bindings") formula.bindings = Object.fromEntries(val.split(",").map((b) => b.trim().split("=")).filter((b) => b.length === 2));
      } else {
        const m = item.match(/^(\w+):\s*`(.+)`$/);
        if (!m) { warnings.push({ line: n, level: "error", message: "Formula must look like: name: `expression`" }); return; }
        formula = { name: m[1], expr: m[2], source: "both", bindings: {} };
        flow.formulas.push(formula);
      }
    }
  });
  closeFlow();
  if (!flows.length) warnings.push({ line: 1, level: "error", message: "No '## Flow:' sections found" });
  for (const f of flows) for (const fo of f.formulas) {
    const names = [...fo.expr.matchAll(/\b[a-z_]\w*\b/g)].map((m) => m[0]);
    for (const b of Object.keys(fo.bindings)) if (!names.includes(b)) warnings.push({ line: flowLine, level: "warning", message: `Binding '${b}' is unused in formula '${fo.name}'` });
  }
  return { parsed: { title, base_url, flows }, warnings };
}
