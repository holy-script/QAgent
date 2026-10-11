import { defineConfig } from "@playwright/test";

const PORT = 3100;

// The suite runs the real production build in demo mode (no backend) with the sign-in screen switched on, so every
// page, form and flow is exercised against the built-in demo data.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 3,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, viewport: { width: 1280, height: 900 }, trace: "retain-on-failure" },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    { name: "signed-out", testMatch: /auth\.spec\.ts/ },
    { name: "app", testIgnore: [/auth\.setup\.ts/, /auth\.spec\.ts/], dependencies: ["setup"], use: { storageState: "e2e/.auth/state.json", permissions: ["clipboard-read", "clipboard-write"] } },
  ],
  webServer: {
    command: `npm run build && npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
    env: { NEXT_PUBLIC_REQUIRE_LOGIN: "true", NEXT_PUBLIC_API_URL: "" },
  },
});
