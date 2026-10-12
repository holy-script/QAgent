import { expect, test as setup } from "@playwright/test";
import { signIn } from "./helpers";

setup("sign in once and keep the session", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("heading", { name: "Your apps" })).toBeVisible();
  // Tours are offered to first-time visitors; the rest of the suite runs as a returning user.
  await page.evaluate(() => localStorage.setItem("qagent_tours", JSON.stringify(["home", "app", "run", "plan", "bug"])));
  await page.context().storageState({ path: "e2e/.auth/state.json" });
});
