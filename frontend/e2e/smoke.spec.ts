import { expect, test } from "@playwright/test";
import { APP, expectAccessible, setTheme } from "./helpers";

// Every page, in both themes: it renders its heading, throws no errors, and has no blocking accessibility problems.
const PAGES: [string, string, string | RegExp][] = [
  ["home", "/", "Your apps"],
  ["help", "/help", "How QAgent works"],
  ["add app", "/apps/new", "Add an app"],
  ["overview", APP, "Test runs"],
  ["test plans", `${APP}/playbooks`, "Test plans"],
  ["add test plan", `${APP}/playbooks/new`, "Add a test plan"],
  ["test plan", `${APP}/playbooks/pb-checkout`, "Checkout flow"],
  ["runs", `${APP}/runs`, "Every time you run a test plan"],
  ["run", `${APP}/runs/run-h3`, "Checkout flow"],
  ["report", `${APP}/runs/run-h3/report`, "Test report"],
  ["journeys", `${APP}/flows`, /passed/],
  ["journey history", `${APP}/flows/add-to-cart`, "add-to-cart"],
  ["compare", `${APP}/compare`, "Compare two runs side by side"],
  ["bugs", `${APP}/issues`, "Bugs found"],
  ["bug", `${APP}/issues/iss-pay`, "Server error on POST /api/pay"],
  ["requirements", `${APP}/traceability`, "Which of your requirements are being tested"],
  ["settings", `${APP}/settings`, "Delete this app"],
];

for (const theme of ["light", "dark"] as const) {
  test.describe(`${theme} theme`, () => {
    for (const [name, path, text] of PAGES) {
      test(`${name} renders and is accessible`, async ({ page }) => {
        const errors: string[] = [];
        page.on("pageerror", (e) => errors.push(e.message));
        page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
        await page.goto(path);
        await setTheme(page, theme);
        await expect(page.getByText(text).first()).toBeVisible();
        await page.waitForTimeout(600); // let client data settle
        await expect(page.locator("html")).toHaveClass(theme === "dark" ? /dark/ : /^((?!dark).)*$/);
        await expectAccessible(page, `${name} (${theme})`);
        expect(errors, "console errors").toEqual([]);
      });
    }
  });
}

test("light is the default theme and the switcher remembers a change", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.getByRole("button", { name: "Change theme" }).click();
  await page.getByRole("menuitem", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Change theme" }).click();
  await page.getByRole("menuitem", { name: "Light" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.getByRole("button", { name: "Change theme" }).click();
  await page.getByRole("menuitem", { name: "Match my device" }).click();
  await expect.poll(() => page.evaluate(() => localStorage.getItem("theme"))).toBe("system");
});

test.describe("phone width", () => {
  test.use({ viewport: { width: 390, height: 800 } });
  for (const [name, path] of [["home", "/"], ["overview", APP], ["bug", `${APP}/issues/iss-pay`], ["run", `${APP}/runs/run-h3`], ["test plan", `${APP}/playbooks/pb-checkout`]]) {
    test(`${name} does not scroll sideways`, async ({ page }) => {
      await page.goto(path);
      await page.waitForTimeout(800);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }
});
