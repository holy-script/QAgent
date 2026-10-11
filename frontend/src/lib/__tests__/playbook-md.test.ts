import { describe, expect, it } from "vitest";
import { SAMPLE_PLAYBOOK } from "@/lib/api/sample-playbook";
import { CATEGORIES, diffLines, extraFieldLines, insertItem, itemMarkdown, itemToValues, nextKey, removeItem, replaceItem } from "@/lib/playbook-md";
import { validateMarkdown } from "@/lib/playbook-validate";

const item = (md: string, key: string) => validateMarkdown(md).items.find((i) => i.key === key)!;

describe("editing the Markdown by item", () => {
  it("adds an item to its section, creating the section when missing", () => {
    const added = insertItem(SAMPLE_PLAYBOOK, "Requirements", itemMarkdown("requirement", "REQ-4", { title: "Orders can be cancelled", acceptance: "A placed order can be cancelled", priority: "high", prd_ref: "" }));
    const v = validateMarkdown(added);
    expect(v.items.filter((i) => i.category === "requirement").map((i) => i.key)).toEqual(["REQ-1", "REQ-2", "REQ-3", "REQ-4"]);
    expect(v.counts.flows).toBe(4); // nothing else moved
    const fresh = insertItem("# Playbook: x\nbase_url: http://a\n", "Gotchas", "### G-1: t\n- note: n\n");
    expect(fresh).toContain("## Gotchas\n### G-1: t");
    expect(validateMarkdown(fresh).counts.gotchas).toBe(1);
  });
  it("removes exactly one item, including a journey with its sub-sections", () => {
    const md = removeItem(SAMPLE_PLAYBOOK, "payment");
    expect(md).not.toContain("### Flow: payment");
    expect(md).not.toContain("Click Pay now");
    expect(md).toContain("### Flow: checkout");
    expect(removeItem(SAMPLE_PLAYBOOK, "REQ-9")).toBe(SAMPLE_PLAYBOOK);
  });
  it("replaces an item in place without disturbing its neighbours", () => {
    const block = itemMarkdown("requirement", "REQ-2", { title: "Payments never fail", acceptance: "No 5xx on payment", priority: "critical", prd_ref: "§5" });
    const md = replaceItem(SAMPLE_PLAYBOOK, "REQ-2", block);
    const v = validateMarkdown(md);
    expect(v.items.filter((i) => i.category === "requirement").map((i) => i.title)).toEqual(["Cart total applies the discount before tax", "Payments never fail", "Checkout requires a valid postal code"]);
    expect(v.errors).toEqual([]);
    expect(md.indexOf("### REQ-2")).toBeGreaterThan(md.indexOf("### REQ-1"));
    expect(md.indexOf("### REQ-2")).toBeLessThan(md.indexOf("### REQ-3"));
  });
  it("numbers new items after the highest existing one", () => {
    expect(nextKey(["REQ-1", "REQ-7", "F-2"], "REQ-")).toBe("REQ-8");
    expect(nextKey([], "UX-")).toBe("UX-1");
  });
});

describe("forms round-trip through the Markdown", () => {
  const cats = CATEGORIES.map((c) => c.id);
  const sample: Record<string, string> = { requirement: "REQ-1", flow: "add-to-cart", formula: "F-1", ux_rule: "UX-1", gotcha: "G-1", edge_case: "EC-2", reasoning_example: "RX-1" };
  it.each(cats)("%s: parsed item -> form values -> Markdown -> same item", (cat) => {
    const original = item(SAMPLE_PLAYBOOK, sample[cat]);
    const values = itemToValues(cat, original);
    const rebuilt = replaceItem(SAMPLE_PLAYBOOK, original.key, itemMarkdown(cat, original.key, values, extraFieldLines(cat, original.body)));
    const again = item(rebuilt, original.key);
    expect(again.title).toBe(original.title);
    expect(again.body).toEqual(original.body);
    expect(validateMarkdown(rebuilt).errors).toEqual([]);
  });
});

describe("diffLines", () => {
  it("marks additions, deletions and unchanged lines", () => {
    expect(diffLines("a\nb\nc", "a\nx\nc")).toEqual([{ type: "same", text: "a" }, { type: "del", text: "b" }, { type: "add", text: "x" }, { type: "same", text: "c" }]);
    expect(diffLines("same", "same").every((l) => l.type === "same")).toBe(true);
  });
});
