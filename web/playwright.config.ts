import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results/playwright",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL: "http://127.0.0.1:5173",
    channel: "msedge",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: path.resolve(__dirname, "../api"),
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      timeout: 30_000,
      env: {
        ...process.env,
        DEMO_OFFLINE: "1",
      },
    },
    {
      command: "pnpm dev --host 127.0.0.1 --port 5173",
      cwd: __dirname,
      url: "http://127.0.0.1:5173/console",
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
