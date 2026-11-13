import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const WEB_DIR = path.resolve(__dirname, "..");
const REPO_DIR = path.resolve(WEB_DIR, "..");
const API_DIR = path.resolve(REPO_DIR, "api");
const OUT_DIR = path.resolve(WEB_DIR, "test-results");
const SCREENSHOT_PATH = path.resolve(OUT_DIR, "console.png");

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForUrl(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // Retry
    }
    await sleep(400);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function launchBrowser() {
  for (const channel of ["msedge", "chrome", undefined]) {
    try {
      return await chromium.launch({
        headless: true,
        ...(channel ? { channel } : {}),
      });
    } catch {
      // Try next channel
    }
  }
  throw new Error("Could not launch Chromium/Edge/Chrome browser.");
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const apiProc = spawn(
    "uv",
    ["run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    {
      cwd: API_DIR,
      env: { ...process.env, DEMO_OFFLINE: "1", DEMO_MODE: "1" },
      stdio: "ignore",
    }
  );

  const viteProc = spawn(
    "node",
    [path.resolve(WEB_DIR, "node_modules/vite/bin/vite.js"), "--port", "5173", "--host", "127.0.0.1"],
    {
      cwd: WEB_DIR,
      env: { ...process.env },
      stdio: "ignore",
    }
  );

  let browser = null;
  try {
    await waitForUrl("http://127.0.0.1:8000/api/health", 30000);
    await waitForUrl("http://127.0.0.1:5173/console", 30000);

    browser = await launchBrowser();
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (text.includes("ERR_NAME_NOT_RESOLVED")) return;
        consoleErrors.push(text);
      }
    });
    page.on("pageerror", (err) => {
      consoleErrors.push(err.message);
    });

    await page.goto("http://127.0.0.1:5173/console", { waitUntil: "networkidle" });

    const runBtn = page.getByRole("button", { name: /Reset and run the flood/i });
    await runBtn.waitFor({ state: "visible", timeout: 10000 });
    await runBtn.click();

    // First wait for the reset to clear any prior run state (clock back to 07:00 IST or <22:00 IST)
    await sleep(1500);

    // At speed=60, 16 hours take ~16s plus end-of-day detector and persona runs (~3s).
    try {
      await page.waitForFunction(
        () => {
          const text = (document.body.textContent || "").toLowerCase();
          return (
            text.includes("22:00 ist") &&
            text.includes("6 of 7 claims filed") &&
            text.includes("simulated consent") &&
            text.includes("simulated reply") &&
            !text.includes("(0 steps)")
          );
        },
        { timeout: 45000 }
      );
    } catch (waitErr) {
      const pageText = await page.evaluate(() => document.body.innerText);
      const apiStreet = await fetch("http://127.0.0.1:8000/api/street/panagal_park_road?day=2026-10-21").then((r) => r.json()).catch(() => null);
      console.error("Wait failed. Clock:", apiStreet?.clock);
      console.error("Page text snippet:", pageText.slice(0, 600));
      throw waitErr;
    }

    // Wait 600ms for shutter and case line animations to settle.
    await sleep(600);

    const dimensions = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      clientHeight: document.documentElement.clientHeight,
    }));

    console.log("Viewport check:", JSON.stringify(dimensions));
    if (dimensions.scrollHeight > 900) {
      throw new Error(
        `Console overflowed 1440x900 viewport: scrollHeight=${dimensions.scrollHeight}`
      );
    }

    await page.screenshot({ path: SCREENSHOT_PATH, fullPage: false });
    console.log(`Saved screenshot to ${SCREENSHOT_PATH}`);

    if (consoleErrors.length > 0) {
      throw new Error(`Console errors detected: ${consoleErrors.join("; ")}`);
    }
  } finally {
    if (browser) {
      await browser.close().catch(() => undefined);
    }
    apiProc.kill();
    viteProc.kill();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

