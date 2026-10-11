import { expect, test as setup } from "@playwright/test";
import { signIn } from "./helpers";

setup("sign in once and keep the session", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("heading", { name: "Your apps" })).toBeVisible();
  await page.context().storageState({ path: "e2e/.auth/state.json" });
});
