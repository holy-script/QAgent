import { expect, test } from "@playwright/test";
import { APP, expectAccessible, finishRun } from "./helpers";

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

test("the AI calls tab lists every model call with its cost and is accessible", async ({ page }) => {
  await page.goto(`${APP}/runs/run-h3`);
  await page.getByRole("tab", { name: "AI calls" }).click();
  await expect(page.getByRole("heading", { name: /^Steps/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Checks/ })).toBeVisible();
  await expect(page.getByText(/AI calls, \$/)).toBeVisible();
  await expectAccessible(page, "ai calls");
});

test("planning is an opt-in choice when starting a run, and hidden for practice runs", async ({ page }) => {
  await page.goto(APP);
  const plan = page.getByRole("checkbox", { name: /plan each journey first/ });
  await expect(plan).not.toBeChecked();
  await page.getByRole("radio", { name: /Practice/ }).click();
  await expect(plan).toHaveCount(0);
});

test("each app sets its own clean-up policy and old runs can be removed", async ({ page }) => {
  await page.goto(APP);
  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByText("10 runs stored; none will be deleted.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Clean up now/ })).toBeDisabled();
  await page.getByLabel("Delete runs older than (days)").fill("0");
  await expect(page.getByText(/Days must be a whole number/)).toBeVisible();
  await page.getByLabel("Delete runs older than (days)").fill("7");
  await page.getByLabel("Always keep the newest runs").fill("2");
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByText("4 of 10 runs would be deleted right now.")).toBeVisible(); // the demo has runs 9, 13, 18 and 24 days old
  await page.getByRole("button", { name: /Clean up now/ }).click();
  await page.getByRole("button", { name: "Delete old runs" }).click();
  await expect(page.getByText("0 of 6 runs would be deleted right now.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Clean up now/ })).toBeDisabled();
});

test("test files: built-in samples are listed and a new file can be added and removed", async ({ page }) => {
  await page.goto(APP);
  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Test files" })).toBeVisible();
  await expect(page.getByRole("cell", { name: /sample\.png/ })).toBeVisible();
  await page.getByLabel("Choose test files").setInputFiles({ name: "invoice.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 demo") });
  await expect(page.getByRole("cell", { name: "invoice.pdf", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Remove invoice.pdf" }).click();
  await expect(page.getByRole("cell", { name: "invoice.pdf", exact: true })).toHaveCount(0);
  await page.getByLabel("Choose test files").setInputFiles({ name: "huge.bin", mimeType: "application/octet-stream", buffer: Buffer.alloc(11 * 1024 * 1024) });
  await expect(page.getByRole("alert").filter({ hasText: "at most 10 MB" })).toBeVisible();
});

test("the home dashboard shows totals, charts, app health and the period switch", async ({ page }) => {
  await page.goto("/");
  const dash = page.getByRole("region", { name: "Dashboard" });
  await expect(dash.getByText("Test runs").first()).toBeVisible();
  await expect(dash.getByText("Open bugs").first()).toBeVisible();
  await expect(dash.getByRole("group", { name: /Runs per day over the last 30 days/ })).toBeVisible();
  await expect(dash.getByRole("heading", { name: "App health" })).toBeVisible();
  await dash.getByRole("button", { name: "7 days" }).click();
  await expect(dash.getByRole("group", { name: /Runs per day over the last 7 days/ })).toBeVisible();
  await dash.getByRole("link", { name: /Demo Shop/ }).first().click();
  await expect(page).toHaveURL(/apps\/demo-shop/);
});

test("on wide screens the app sections sit in a side list; on a phone they are tabs", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(APP);
  const nav = page.getByRole("navigation", { name: "Sections" });
  await expect(nav).toHaveCount(1);
  expect((await nav.boundingBox())!.width).toBeLessThan(260);
  await page.setViewportSize({ width: 390, height: 800 });
  await expect(page.getByRole("navigation", { name: "Sections" })).toHaveCount(1);
  expect((await page.getByRole("navigation", { name: "Sections" }).boundingBox())!.width).toBeGreaterThan(300);
});

test.describe("guided tours", () => {
  const popover = (page: import("@playwright/test").Page) => page.locator(".driver-popover");

  test("the Tour button walks through the page and Esc stops it", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Take a tour of this page" }).click();
    await expect(popover(page).getByText("Welcome to QAgent")).toBeVisible();
    await popover(page).getByRole("button", { name: "Next" }).click();
    await expect(popover(page).getByText("How testing is going")).toBeVisible();
    await expect(popover(page).getByText(/2 of \d/)).toBeVisible();
    await popover(page).getByRole("button", { name: "Back" }).click();
    await expect(popover(page).getByText("Welcome to QAgent")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(popover(page)).toHaveCount(0);
  });

  test("an app page has its own tour and it finishes with Done", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(APP);
    await page.getByRole("button", { name: "Take a tour of this page" }).click();
    await expect(popover(page).getByText("An app's workspace")).toBeVisible();
    for (let i = 0; i < 20; i++) {
      const button = popover(page).getByRole("button", { name: /^(Next|Done)$/ });
      if ((await button.innerText()) === "Done") break;
      await button.click();
    }
    await expect(popover(page).getByText("Run a test")).toBeVisible();
    await popover(page).getByRole("button", { name: "Done" }).click();
    await expect(popover(page)).toHaveCount(0);
  });

  test("on a phone the tour skips parts that are not on screen", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(APP);
    await page.getByRole("button", { name: "Take a tour of this page" }).click();
    await expect(popover(page).getByText("An app's workspace")).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("a link with ?tour= starts that tour, and first-time visitors are offered one", async ({ page, context }) => {
    await page.goto("/?tour=home");
    await expect(popover(page).getByText("Welcome to QAgent")).toBeVisible();
    await page.keyboard.press("Escape");
    // a new visitor (no tours seen), in a normal (non-automated) browser, is offered the tour on their first page
    await context.addInitScript(() => { localStorage.removeItem("qagent_tours"); Object.defineProperty(navigator, "webdriver", { get: () => false }); });
    await page.goto("/");
    await expect(popover(page).getByText("Welcome to QAgent")).toBeVisible({ timeout: 8000 });
  });
});
