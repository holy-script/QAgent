import { expect, test } from "@playwright/test";
import { ACCOUNT, signIn } from "./helpers";

test.describe("signing in and out", () => {
  test("visitors are sent to the sign-in page and brought back afterwards", async ({ page }) => {
    await page.goto("/apps/demo-shop/issues");
    await expect(page).toHaveURL(/\/login\?next=%2Fapps%2Fdemo-shop%2Fissues/);
    await expect(page.getByRole("heading", { name: "Sign in to QAgent" })).toBeVisible();
    await page.getByLabel("Email").fill(ACCOUNT.email);
    await page.getByLabel("Password", { exact: true }).fill(ACCOUNT.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/apps\/demo-shop\/issues$/);
    await expect(page.getByRole("heading", { name: "Bugs found" })).toBeVisible();
  });

  test("wrong credentials show one plain message and keep you on the page", async ({ page }) => {
    await page.goto("/login");
    const submit = page.getByRole("button", { name: "Sign in" });
    await expect(submit).toBeDisabled(); // nothing typed yet
    await page.getByLabel("Email").fill(ACCOUNT.email);
    await page.getByLabel("Password", { exact: true }).fill("wrong");
    await submit.click();
    await expect(page.locator("p[role=alert]")).toHaveText("Email or password is not correct");
    await expect(page).toHaveURL(/\/login/);
    await page.getByLabel("Email").fill("someone@else.com");
    await page.getByLabel("Password", { exact: true }).fill(ACCOUNT.password);
    await submit.click();
    await expect(page.locator("p[role=alert]")).toHaveText("Email or password is not correct");
  });

  test("the password can be shown and hidden, and the email is not case sensitive", async ({ page }) => {
    await page.goto("/login");
    const pw = page.getByLabel("Password", { exact: true });
    await pw.fill(ACCOUNT.password);
    await expect(pw).toHaveAttribute("type", "password");
    await page.getByRole("button", { name: "Show password" }).click();
    await expect(pw).toHaveAttribute("type", "text");
    await page.getByRole("button", { name: "Hide password" }).click();
    await page.getByLabel("Email").fill("  ADMIN@Chryselys.com ");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Your apps" })).toBeVisible();
  });

  test("signing out ends the session", async ({ page }) => {
    await signIn(page);
    await expect(page.getByRole("heading", { name: "Your apps" })).toBeVisible();
    await page.getByRole("button", { name: "Account" }).click();
    await expect(page.getByText(ACCOUNT.email)).toBeVisible();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/apps/demo-shop");
    await expect(page).toHaveURL(/\/login\?next=/);
  });

  test("the help page is readable without signing in", async ({ page }) => {
    await page.goto("/help");
    await expect(page.getByRole("heading", { name: "How QAgent works" })).toBeVisible();
    await expect(page.getByText("The five-minute path")).toBeVisible();
    await expect(page.getByText("Words you will see")).toBeVisible();
  });
});
