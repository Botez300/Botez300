import { defineConfig } from "playwright/test";

// Expects the stack to be running (see README: `make dev` or docker compose). BASE_URL overrides the target.
export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  outputDir: process.env.E2E_OUTPUT ?? "test-results",
  use: { baseURL: process.env.BASE_URL ?? "http://localhost:3000", viewport: { width: 1440, height: 900 }, trace: "off" },
});
