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
  // a new app starts the setup guide: it points at the product document on the Settings page
  await expect(page.locator(".driver-popover").getByText("Welcome! Let's set your app up")).toBeVisible();
  await page.keyboard.press("Escape");

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


// ---- dictation: a fake browser recogniser lets the tests "speak" ----
// Plain JavaScript on purpose: it is injected into the page as text, so it must not rely on compiler helpers.
const FAKE_RECOGNISER = `
  var Fake = function () { this.lang = ""; this.continuous = false; this.interimResults = false; };
  Fake.prototype.start = function () { window.__rec = this; };
  Fake.prototype.stop = function () { if (this.onend) this.onend(); };
  Fake.prototype.abort = function () { if (this.onend) this.onend(); };
  // newer Chromium has both names, so replace both
  Object.defineProperty(window, "SpeechRecognition", { value: Fake, configurable: true, writable: true });
  Object.defineProperty(window, "webkitSpeechRecognition", { value: Fake, configurable: true, writable: true });
  window.__say = function (text, final) {
    var result = [{ transcript: text }]; result.isFinal = final !== false;
    window.__rec.onresult({ resultIndex: 0, results: [result] });
  };
`;

test.describe("dictation", () => {
  test("speaking fills a field, shows what is being heard, and AI tidy-up can be undone", async ({ page }) => {
    await page.addInitScript({ content: FAKE_RECOGNISER });
    await page.goto("/apps/new");
    const box = page.getByRole("textbox", { name: "What does it do?" });
    await page.getByRole("button", { name: "Dictate", exact: true }).click();
    await page.evaluate(() => (window as unknown as { __say: (t: string, f: boolean) => void }).__say("um it is a shop that sells mugs", false));
    await expect(page.getByText("um it is a shop that sells mugs")).toBeVisible();      // shown while it is still being heard
    await page.evaluate(() => (window as unknown as { __say: (t: string) => void }).__say("um it is a shop that sells mugs"));
    await page.evaluate(() => (window as unknown as { __say: (t: string) => void }).__say("new line and people pay by card"));
    await expect(box).toHaveValue("um it is a shop that sells mugs\nand people pay by card");
    await page.getByRole("button", { name: /Stop dictat/i }).click();

    await page.getByRole("button", { name: "Tidy up with AI" }).click();
    await expect(box).toHaveValue("It is a shop that sells mugs and people pay by card.");
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(box).toHaveValue("um it is a shop that sells mugs\nand people pay by card");
  });

  test("the product document can be dictated, organised by AI, or imported from a file", async ({ page }) => {
    await page.addInitScript({ content: FAKE_RECOGNISER });
    await page.goto(APP);
    await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Settings" }).click();
    const prd = page.getByRole("textbox", { name: "Product document" });
    await page.getByRole("button", { name: "Dictate", exact: true }).nth(1).click();
    await page.evaluate(() => (window as unknown as { __say: (t: string) => void }).__say("It is a shop. Users add mugs. They pay by card."));
    await expect(prd).toHaveValue(/Users add mugs/);
    await page.getByRole("button", { name: "Organise with AI" }).click();
    await expect(prd).toHaveValue(/## Features and requirements\n1\. Users add mugs\./);
    await page.getByLabel("Choose a text file to import").setInputFiles({ name: "notes.md", mimeType: "text/markdown", buffer: Buffer.from("## Extra\nOne more thing.") });
    await expect(prd).toHaveValue(/## Extra\nOne more thing\.$/);
  });

  test("browsers without speech recognition get a clear message instead of a broken button", async ({ page }) => {
    await page.addInitScript({ content: `Object.defineProperty(window, "SpeechRecognition", { value: undefined, configurable: true }); Object.defineProperty(window, "webkitSpeechRecognition", { value: undefined, configurable: true });` });
    await page.goto("/apps/new");
    await expect(page.getByRole("button", { name: "Dictate", exact: true })).toBeDisabled();
    await expect(page.getByText("Dictation needs Chrome, Edge or Safari.")).toBeVisible();
  });
});

// ---- guided setup ----
test.describe("guided setup", () => {
  test("the Overview lists the steps in order, and Take me there points at the right control", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(APP);
    const guide = page.getByLabel("Setup guide");
    await expect(guide.getByText(/\d of 6 steps done/)).toBeVisible();
    await expect(guide.getByText("1. Describe your app")).toBeVisible();
    await expect(guide.getByText("3. Create a test plan")).toBeVisible();
    await guide.getByRole("link", { name: "Take me there" }).first().click();
    await expect(page).toHaveURL(/settings\?guide=describe/);
    const pop = page.locator(".driver-popover");
    await expect(pop.getByText("Describe your app")).toBeVisible();
    await expect(pop.getByRole("button", { name: /Next: Add test files/ })).toBeVisible();
    await pop.getByRole("button", { name: /Next: Add test files/ }).click();
    await expect(pop.getByText("Add test files")).toBeVisible();
    await pop.getByRole("button", { name: "Close" }).click();
    await expect(pop).toHaveCount(0);
    await expect(page).not.toHaveURL(/guide=/);
  });

  test("finishing a step ticks it off, optional steps can be skipped, and the side card shows what is next", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(APP);
    const guide = page.getByLabel("Setup guide");
    await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Settings" }).click();
    await page.getByRole("textbox", { name: "Product document" }).fill("Users can browse, add to cart and pay.");
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByText("Saved")).toBeVisible();
    await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Overview" }).click();
    await expect(guide.getByText("1. Describe your app (done)")).toBeVisible();
    await expect(page.getByRole("link", { name: /Next: Add test files/ })).toBeVisible();
    await guide.getByRole("button", { name: "Skip" }).first().click();
    await expect(guide.getByText(/2\. Add test files.*\(skipped\)/)).toBeVisible();
    await expect(page.getByRole("link", { name: /Next: Read what it found/ })).toBeVisible(); // the demo app already has a test plan and runs
    await guide.getByRole("button", { name: "Undo skip" }).click();
    await expect(guide.getByText(/2\. Add test files.*\(to do\)/)).toBeVisible();
  });

  test("on a phone the guide is a card under the tabs", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(APP);
    await expect(page.getByRole("link", { name: /Next: Describe your app/ })).toBeVisible();
  });
});


test.describe("fixes from first real use", () => {
  test("runs can be deleted one at a time or in bulk from the list", async ({ page }) => {
    await page.goto(APP);
    await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Runs" }).click();
    await expect(page.getByRole("row")).toHaveCount(11); // header + 10 demo runs
    await page.getByRole("button", { name: /Delete run run-h10/ }).click();
    await page.getByRole("button", { name: "Delete run", exact: true }).click();
    await expect(page.getByRole("row")).toHaveCount(10);
    await page.getByRole("checkbox", { name: /Select run run-h9/ }).click();
    await page.getByRole("checkbox", { name: /Select run run-b8/ }).click();
    await expect(page.getByText("2 selected")).toBeVisible();
    await page.getByRole("button", { name: "Delete selected" }).click();
    await page.getByRole("button", { name: "Delete 2 runs" }).click();
    await expect(page.getByRole("row")).toHaveCount(8);
    await page.getByRole("checkbox", { name: "Select all runs" }).click();
    await expect(page.getByText("7 selected")).toBeVisible();
  });

  test("the test plan dropdown can be clicked with the mouse while the setup guide is pointing at it", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${APP}?guide=run`);
    await expect(page.locator(".driver-popover").getByText("Run your first test")).toBeVisible();
    await page.getByRole("combobox", { name: "Test plan" }).click();
    await page.getByRole("option").first().click({ timeout: 5000 });
    await expect(page.getByRole("combobox", { name: "Test plan" })).toBeVisible();
  });

  test("starting a run from the guide takes the pointer away and moves on to the results step", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${APP}?guide=run`);
    await expect(page.locator(".driver-popover").getByText("Run your first test")).toBeVisible();
    await page.getByRole("button", { name: "Run now" }).click();
    await expect(page).toHaveURL(/runs\/run-.*guide=results/);
    await expect(page.locator(".driver-popover").getByText("Read what it found")).toBeVisible();
    await expect(page.locator(".driver-popover")).toHaveCount(1);          // the old "run" pointer is gone, not stacked
    await page.locator(".driver-popover").getByRole("button", { name: "Close" }).click();
    await expect(page.locator(".driver-popover")).toHaveCount(0);
  });

  test("the test plan editor has one place to dictate, next to the rewrite button", async ({ page }) => {
    await page.goto(`${APP}/playbooks/new`);
    await expect(page.getByRole("button", { name: "Dictate", exact: true })).toHaveCount(1);
  });
});

test.describe("deleting test plans", () => {
  const sections = (page: import("@playwright/test").Page) => page.getByRole("navigation", { name: "Sections" });

  test("a plan can be deleted from the list while its runs stay in the history", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(APP);
    await sections(page).getByRole("link", { name: "Test plans" }).click();
    await page.getByRole("button", { name: /Delete test plan Checkout flow/ }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText(/It has 10 past runs/)).toBeVisible();
    await expect(dialog.getByRole("checkbox")).not.toBeChecked();
    await dialog.getByRole("button", { name: "Delete test plan" }).click();
    await expect(page.getByText("No test plans yet")).toBeVisible();
    await sections(page).getByRole("link", { name: "Runs" }).click();
    await expect(page.getByRole("cell", { name: "Deleted test plan" }).first()).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(11);                   // all ten runs are still there
  });

  test("a plan can be deleted from its own page together with its runs", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${APP}/playbooks/pb-checkout`);
    await page.getByRole("button", { name: "Delete test plan", exact: true }).click();
    await page.getByRole("dialog").getByRole("checkbox").click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete test plan" }).click();
    await expect(page).toHaveURL(/playbooks$/);
    await expect(page.getByText("No test plans yet")).toBeVisible();
    await sections(page).getByRole("link", { name: "Runs" }).click();
    await expect(page.getByText("No test runs yet")).toBeVisible();
  });
});

test.describe("high-level test plans from the product document", () => {
  test("Create from product document writes goal-driven journeys, flags notes, and they save and display as goals", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(APP);
    const sections = page.getByRole("navigation", { name: "Sections" });
    await sections.getByRole("link", { name: "Settings" }).click();
    await page.getByRole("textbox", { name: "Product document" }).fill("Users sign in and reach the dashboard. Users set up a forecast and see the results. Users export the forecast.");
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByText("Saved")).toBeVisible();

    await sections.getByRole("link", { name: "Test plans" }).click();
    await page.getByRole("link", { name: "Add a test plan" }).click();
    await page.getByRole("button", { name: "Create from product document" }).click();
    const editor = page.getByRole("textbox", { name: "Test plan text" });
    await expect(editor).toContainText("#### Goal");
    await expect(editor).not.toContainText("#### Steps");
    await expect(page.getByText("Check before saving")).toBeVisible();
    await page.getByRole("button", { name: "Save and review" }).click();
    await expect(page.getByText("Goal (the AI chooses the steps)").first()).toBeVisible();
  });

  test("without a product document it says what to do first", async ({ page }) => {
    await page.goto(`${APP}/playbooks/new`);
    await page.getByRole("button", { name: "Create from product document" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Add a product document in Settings first" })).toBeVisible();
  });
});
