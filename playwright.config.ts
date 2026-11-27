import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  retries: 1,
  workers: 1, // stay well inside the API's rate limit
  use: {
    baseURL: process.env.BASE_URL ?? "https://quant-project-2.vercel.app",
    // PW_CHANNEL=chrome uses an installed Google Chrome instead of Playwright's browser
    channel: process.env.PW_CHANNEL || undefined,
  },
});
