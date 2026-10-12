import { describe, expect, it } from "vitest";
import { appendDictation, applyVoiceCommands } from "@/lib/dictation";
import { mockRefine } from "@/lib/refine-mock";

describe("dictation text handling", () => {
  it("turns spoken line commands into line breaks", () => {
    expect(applyVoiceCommands("first item new line second item new paragraph third")).toBe("first item\nsecond item\n\nthird");
    expect(applyVoiceCommands("a brand new lineup")).toBe("a brand new lineup"); // only the whole phrase counts
  });
  it("joins phrases with sensible spacing", () => {
    expect(appendDictation("", "  hello there ")).toBe("hello there");
    expect(appendDictation("hello", "there")).toBe("hello there");
    expect(appendDictation("hello ", "there")).toBe("hello there");
    expect(appendDictation("hello", "new line there")).toBe("hello\nthere");
    expect(appendDictation("keep", "   ")).toBe("keep");
  });
});

describe("demo-mode tidy-up", () => {
  const raw = "um the cart should show the total  you know and the badge should match the items";
  it("removes filler, capitalises and punctuates", () => {
    expect(mockRefine(raw, "tidy").text).toBe("The cart should show the total and the badge should match the items.");
  });
  it("shapes the text for its purpose", () => {
    expect(mockRefine("It is a shop. Users add mugs. They pay by card.", "description").text).toBe("It is a shop. Users add mugs.");
    expect(mockRefine("It is a shop. Users add mugs.", "notes").text).toBe("- It is a shop.\n- Users add mugs.");
    const prd = mockRefine("It is a shop. Users add mugs. They pay by card.", "prd").text;
    expect(prd).toContain("## Overview\nIt is a shop.");
    expect(prd).toContain("1. Users add mugs.\n2. They pay by card.");
    expect(mockRefine("   ", "tidy").text).toBe("");
  });
});
