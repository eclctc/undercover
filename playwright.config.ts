import { defineConfig } from "@playwright/test";

export const BACKEND_URL = "http://127.0.0.1:8001";
const env = { UNDERCOVER_DB: "e2e/e2e.db", BACKEND_URL };

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command:
        "uv run -m backend.seed && uv run -m uvicorn backend.main:app --port 8001",
      url: `${BACKEND_URL}/api/health`,
      env,
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      env,
      reuseExistingServer: false,
    },
  ],
});
