import { expect, test } from "@playwright/test";
import { APP, finishRun } from "./helpers";

// Each test is a user journey on the built-in demo data (no backend).

test("add an app, see it listed, then delete it by typing its name", async ({ page }) => {
  await page.goto("/apps/new");
  await expect(page.getByRole("button", { name: "Add app" })).toBeDisabled();
  await page.getByLabel("Name").fill("Scratch Shop");
  await page.getByLabel("Website address").fill("not a url");
  await expect(page.getByText("Enter a full URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add app" })).toBeDisabled();
  await page.getByLabel("Website address").fill("http://localhost:9000");
  await page.getByRole("button", { name: "Add app" }).click();
  await expect(page.getByRole("heading", { name: "Scratch Shop" })).toBeVisible();

  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Settings" }).click(); // demo data lives in memory, so navigate in-app
  await page.getByRole("button", { name: /Delete Scratch Shop/ }).click();
  const confirm = page.getByRole("button", { name: "Delete everything" });
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Type the name to confirm").fill("Scratch Shop");
  await confirm.click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Scratch Shop")).toHaveCount(0);
});

test("the test plan editor flags a broken plan", async ({ page }) => {
  await page.goto(`${APP}/playbooks/pb-checkout`);
  await expect(page.getByText("Checkout flow").first()).toBeVisible();
  await page.getByRole("button", { name: "Edit test plan" }).click();
  const editor = page.getByRole("textbox", { name: "Test plan text" });
  await editor.click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.type("# Nothing useful here");
  await expect(page.getByText(/problem|missing|unknown/i).first()).toBeVisible();
});

test("a run plays back to the end and its report opens", async ({ page }) => {
  await page.goto(`${APP}/runs/run-h3`);
  await page.getByRole("button", { name: "Watch again" }).click();
  await finishRun(page);
  await page.goto(`${APP}/runs/run-h3/report`);
  await expect(page.getByText("Test report").first()).toBeVisible();
});

test("bugs list opens a bug with its evidence", async ({ page }) => {
  await page.goto(`${APP}/issues`);
  await page.getByRole("link", { name: /Server error on POST \/api\/pay/ }).first().click();
  await expect(page).toHaveURL(/issues\/iss-pay/);
  await expect(page.getByRole("heading", { name: /Server error on POST \/api\/pay/ })).toBeVisible();
});

test("the search palette jumps to a page", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  await page.getByPlaceholder("Search pages, runs and bugs…").fill("Demo Shop: Settings");
  await page.getByRole("option", { name: /Demo Shop: Settings/ }).click();
  await expect(page).toHaveURL(/settings/);
});

test("every section of an app is reachable from its tabs", async ({ page }) => {
  await page.goto(APP);
  for (const [name, url] of [["Test plans", /playbooks/], ["Runs", /runs/], ["Journeys", /flows/], ["Bugs", /issues/], ["Requirements", /traceability/], ["Compare", /compare/], ["Settings", /settings/]] as const) {
    await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name }).click();
    await expect(page).toHaveURL(url);
  }
});

test("signing out returns to the sign-in page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Account" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/login/);
});
