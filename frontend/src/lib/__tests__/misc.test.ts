import { describe, expect, it, vi } from "vitest";
import { lineForMessage } from "@/components/live/markdown-editor";
import { SAMPLE_PLAYBOOK } from "@/lib/api/sample-playbook";
import { CATEGORY_LABEL, GLOSSARY, ISSUE_STATUS, MODE_INFO } from "@/lib/terms";
import { THEME_SCRIPT } from "@/lib/theme";
import { ago, fmtBytes, fmtMs, fmtUsd } from "@/components/ui/format";

describe("problem messages point at the right line", () => {
  const line = (n: number) => SAMPLE_PLAYBOOK.split("\n")[n - 1];
  it("finds the heading of the item a message is about", () => {
    expect(line(lineForMessage(SAMPLE_PLAYBOOK, "F-1: variable 'x' has no binding")!)).toBe("### F-1: cart_total");
    expect(line(lineForMessage(SAMPLE_PLAYBOOK, "flow payment: needs a goal or steps")!)).toBe("### Flow: payment");
    expect(line(lineForMessage(SAMPLE_PLAYBOOK, "EC-3: applies_to 'nowhere' does not exist")!)).toBe("### EC-3: Missing postal code");
  });
  it("returns null when it cannot tell", () => {
    expect(lineForMessage(SAMPLE_PLAYBOOK, "something general")).toBeNull();
    expect(lineForMessage(SAMPLE_PLAYBOOK, "ZZ-9: not in the file")).toBeNull();
  });
});

describe("plain-language vocabulary", () => {
  it("explains every mode and bug status", () => {
    expect(Object.keys(MODE_INFO).sort()).toEqual(["baseline", "hybrid", "stub"]);
    Object.values(MODE_INFO).forEach((m) => expect(m.hint.length).toBeGreaterThan(30));
    expect(Object.keys(ISSUE_STATUS)).toEqual(["open", "regressed", "resolved"]);
    expect(ISSUE_STATUS.regressed.label).toBe("Came back");
  });
  it("labels every playbook category and defines the key terms", () => {
    expect(Object.keys(CATEGORY_LABEL)).toHaveLength(7);
    ["Test plan", "Journey", "Bug", "Proof", "Mode"].forEach((t) => expect(GLOSSARY.some((g) => g.term.startsWith(t))).toBe(true));
  });
});

describe("theme and formatting helpers", () => {
  it("defaults to light before first paint", () => {
    expect(THEME_SCRIPT).toContain('||"light"');
    expect(THEME_SCRIPT).toContain('classList.toggle("dark"');
  });
  it("formats durations, sizes, money and ages", () => {
    expect([fmtMs(250), fmtMs(2600), fmtBytes(512), fmtBytes(2048), fmtUsd(0.0094), fmtUsd(1.5)]).toEqual(["250ms", "2.6s", "512 B", "2.0 KB", "$0.0094", "$1.50"]);
    expect(ago(new Date(Date.now() - 5 * 60_000).toISOString())).toBe("5m ago");
    expect(ago(new Date().toISOString())).toBe("just now");
  });
});

describe("same-origin deployment", () => {
  it("treats /api as the API base but serves screenshots from the host root", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "/api");
    const c = await import("../api/client");
    expect(c.USE_MOCK).toBe(false);
    expect(c.API_URL).toBe("/api");
    expect(c.API_ORIGIN).toBe("");
    vi.unstubAllEnvs();
  });
});

describe("clean-up policy (demo mode mirrors the backend rule)", () => {
  it("removes old finished runs, but never the newest N or runs in progress", async () => {
    const { expiredMock } = await import("../api/client");
    const day = 86_400_000;
    const mk = (id: string, ageDays: number, status = "passed") => ({ id, status, started_at: new Date(Date.now() - ageDays * day).toISOString() });
    const runs = [mk("a", 40), mk("b", 35), mk("c", 30), mk("d", 2), mk("e", 1), mk("live", 90, "running")] as never[];
    const app = { retention_days: 7, retention_keep_last: 2 } as never;
    expect(expiredMock(app, runs).map((r: { id: string }) => r.id)).toEqual(["a", "b", "c"]);
    expect(expiredMock({ retention_days: null, retention_keep_last: 2 } as never, runs)).toEqual([]);
  });
});
