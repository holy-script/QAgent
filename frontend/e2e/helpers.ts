import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export const ACCOUNT = { email: "admin@chryselys.com", password: "Admin@QAgent!2026" };
export const APP = "/apps/demo-shop";

export async function signIn(page: Page, to = "/") {
  await page.goto(`/login?next=${encodeURIComponent(to)}`);
  await page.getByLabel("Email").fill(ACCOUNT.email);
  await page.getByLabel("Password", { exact: true }).fill(ACCOUNT.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Fails the test if the page has accessibility problems that block people (serious or critical). */
export async function expectAccessible(page: Page, label: string) {
  // Fades and slides would make colour checks read half-transparent text, so freeze motion first.
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const blocking = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(blocking.map((v) => `${label}: ${v.id} (${v.impact}) ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), "accessibility").toEqual([]);
}

export async function setTheme(page: Page, theme: "light" | "dark") {
  await page.evaluate((t) => { localStorage.setItem("theme", t); window.dispatchEvent(new StorageEvent("storage", { key: "theme" })); }, theme);
}

/** Runs the scripted demo run at top speed and waits until it has finished playing. */
export async function finishRun(page: Page) {
  await page.getByRole("group", { name: "Playback speed" }).getByRole("button", { name: "10×" }).click();
  await expect(page.getByRole("button", { name: "Watch again" })).toBeVisible({ timeout: 45_000 });
}
