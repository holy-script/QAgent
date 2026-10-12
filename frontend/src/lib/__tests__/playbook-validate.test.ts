import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { SAMPLE_PLAYBOOK } from "@/lib/api/sample-playbook";
import { toParsedFlows, validateMarkdown } from "@/lib/playbook-validate";

const FILE = readFileSync(new URL("../../../../playbooks/checkout.md", import.meta.url), "utf8");
const parse = (replace: [string, string][] = []) => validateMarkdown(replace.reduce((t, [a, b]) => { if (!t.includes(a)) throw new Error(`test setup: missing "${a}"`); return t.split(a).join(b); }, FILE));

describe("sample playbook", () => {
  it("is identical to playbooks/checkout.md (regenerate sample-playbook.ts if this fails)", () => {
    expect(SAMPLE_PLAYBOOK).toBe(FILE);
  });
  it("parses into all seven categories with no errors or warnings", () => {
    const v = parse();
    expect([v.title, v.base_url]).toEqual(["Checkout", "http://localhost:8001"]);
    expect(Object.values(v.counts)).toEqual([3, 4, 1, 4, 2, 2, 1]);
    expect(v.errors).toEqual([]);
    expect(v.warnings).toEqual([]);
    const f1 = v.items.find((i) => i.key === "F-1")!;
    expect(f1.body.verifies).toEqual(["REQ-1"]);
    expect((f1.body.bindings as Record<string, string>).tax_rate).toBe("const:0.08");
    expect(v.items.find((i) => i.key === "RX-1")!.body.strategy).toHaveLength(4);
  });
  it("derives coverage and links the way the backend does", () => {
    const v = parse();
    expect(v.coverage.covered_by["REQ-1"]).toEqual(["F-1", "add-to-cart", "apply-coupon", "EC-2"]);
    expect(v.coverage.covered_by["REQ-2"]).toEqual(["payment"]);
    expect(v.links).toContainEqual({ from_key: "EC-3", to_key: "checkout", relation: "applies_to" });
    expect(v.links).toContainEqual({ from_key: "add-to-cart", to_key: "UX-1", relation: "checks" });
  });
  it("builds journey cards for the review page", () => {
    const flows = toParsedFlows(parse());
    expect(flows.map((f) => f.key)).toEqual(["add-to-cart", "apply-coupon", "payment", "checkout"]);
    expect(flows[0].formulas[0].expr).toContain("total ==");
    expect(flows[3].edge_cases).toEqual(["EC-3: Missing postal code"]);
  });
});

describe("validation errors block, warnings do not (same cases as the backend tests)", () => {
  const cases: [string, [string, string][], string][] = [
    ["duplicate id", [["### REQ-2:", "### REQ-1:"]], "REQ-1: ID is defined 2 times"],
    ["unknown reference", [["- verifies: REQ-1", "- verifies: REQ-9"]], "REQ-9' does not exist"],
    ["unbound variable", [["(1 + tax_rate)", "(1 + tax_rate + shipping)"]], "variable 'shipping' has no binding"],
    ["forbidden function", [["round((sum", "open((sum"]], "may be called"],
    ["unknown ux check", [["- check: max_wait\n- max_ms: 2500", "- check: wobble"]], "unknown check type 'wobble'"],
    ["missing ux field", [["- check: max_wait\n- max_ms: 2500", "- check: max_wait"]], "needs field 'max_ms'"],
    ["bad regex", [["- pattern: ^\\$", "- pattern: ^(\\$"]], "pattern does not compile"],
    ["edge case for a missing flow", [["- applies_to: checkout", "- applies_to: nowhere"]], "'nowhere' does not exist"],
  ];
  it.each(cases)("%s", (_name, replace, expected) => {
    expect(parse(replace).errors.some((e) => e.includes(expected))).toBe(true);
  });
  it("warns about uncovered requirements without blocking", () => {
    const v = parse([["- covers: REQ-2\n- severity: critical", "- severity: critical"]]);
    expect(v.errors).toEqual([]);
    expect(v.warnings.some((w) => w.includes("REQ-2") && w.includes("not covered"))).toBe(true);
    expect(v.coverage.uncovered).toEqual(["REQ-2"]);
  });
  it("warns about unknown fields and sections, and flags a renamed journey", () => {
    const v = parse([["- severity: low\n\n## Gotchas", "- severity: low\n- colour: red\n\n## Mystery\n### G-9: x\n- note: y\n\n## Gotchas"]]);
    expect(v.warnings).toContain("UX-4: unknown field 'colour'");
    expect(v.warnings).toContain("unknown section 'Mystery'");
    const renamed = validateMarkdown(FILE.replace("### Flow: payment", "### Flow: pay-now"), validateMarkdown(FILE));
    expect(renamed.warnings.some((w) => w.includes("renamed"))).toBe(true);
  });
  it("reports malformed headings and empty journeys", () => {
    expect(validateMarkdown("## Flows\n### Checkout\n").errors[0]).toContain("must be 'Flow: <key>'");
    expect(validateMarkdown("## Flows\n### Flow: a\n- severity: high\n").errors).toContain("flow a: needs a goal or steps");
    expect(validateMarkdown("## Requirements\n### F-1: wrong prefix\n").errors[0]).toContain("needs an ID like REQ-1");
  });
});

import { itemMarkdown, itemToValues } from "@/lib/playbook-md";
import { mockPlanFromPrd } from "@/lib/refine-mock";

describe("goal-driven journeys", () => {
  const md = "## Requirements\n### REQ-1: Sign in works\n- acceptance: A user can sign in.\n- priority: high\n\n## Flows\n### Flow: sign-in\n- covers: REQ-1\n- severity: high\n\n#### Goal\nSign in and reach the dashboard.\n\n#### Expect\n- The dashboard is shown\n\n#### Test data\n- username: admin\n";
  it("accepts a goal instead of steps, and still rejects a journey with neither", () => {
    const ok = validateMarkdown(md);
    expect(ok.errors).toEqual([]);
    expect(ok.flows[0]).toMatchObject({ goal: "Sign in and reach the dashboard.", steps: [] });
    expect(validateMarkdown(md.replace("#### Goal\nSign in and reach the dashboard.\n\n", "")).errors).toContain("flow sign-in: needs a goal or steps");
    expect(ok.warnings.filter((w) => w.includes("unknown field"))).toEqual([]);
  });
  it("writes and re-reads a goal in the guided form", () => {
    const text = itemMarkdown("flow", "", { title: "sign-in", severity: "high", covers: "REQ-1", checks: "", goal: "Sign in and reach the dashboard.", steps: "", expect: "The dashboard is shown", test_data: "" }, "");
    expect(text).toContain("#### Goal\nSign in and reach the dashboard.");
    expect(text).not.toContain("#### Steps");
    const back = itemToValues("flow", { key: "sign-in", title: "sign-in", body: { goal: "Sign in and reach the dashboard.", steps: [], expect: ["x"], test_data: {} } });
    expect(back.goal).toBe("Sign in and reach the dashboard.");
  });
  it("the demo-mode plan from a product document is a valid plan made of goals", () => {
    const plan = mockPlanFromPrd("Users sign in. Users set up a forecast. They export results.", "http://localhost:8001");
    const v = validateMarkdown(plan.markdown);
    expect(v.errors).toEqual([]);
    expect(v.flows).toHaveLength(3);
    expect((v.flows as { goal?: string; steps: string[] }[]).every((f) => !!f.goal && f.steps.length === 0)).toBe(true);
    expect(plan.markdown).not.toContain("#### Steps");
  });
});
