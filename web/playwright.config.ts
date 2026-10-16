import { defineConfig, devices } from "@playwright/test";

// Runs against the real database from `make load`, with today fixed so the
// reconciliation week is "Last Week".
export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  fullyParallel: false,
  use: { baseURL: "http://localhost:5174", ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: "python3 -m uvicorn api.main:app --port 8766",
      cwd: "..",
      url: "http://localhost:8766/api/freshness",
      // Ask the data replays a fixture recording, never a live model.
      env: {
        DEV_USER: "nick@dev",
        APP_TODAY: "2026-10-05",
        ASK_CLIENT: "recorded",
        ASK_RECORDINGS_DIR: "web/e2e/recordings",
      },
      reuseExistingServer: false,
    },
    {
      command: "npx vite --port 5174 --strictPort",
      url: "http://localhost:5174",
      env: { API_URL: "http://localhost:8766" },
      reuseExistingServer: false,
    },
  ],
});
