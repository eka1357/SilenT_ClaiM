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

const CONSOLE_PNG = path.resolve(OUT_DIR, "console.png");
const MERCHANT_ASK_PNG = path.resolve(OUT_DIR, "merchant-ask.png");
const MERCHANT_MOBILE_PNG = path.resolve(OUT_DIR, "merchant-mobile.png");
const ADJUSTER_PNG = path.resolve(OUT_DIR, "adjuster.png");

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
      env: {
        ...process.env,
        DEMO_OFFLINE: "1",
        DEMO_MODE: "1",
        PAYBACK_ENABLED: "1",
      },
      stdio: "ignore",
    }
  );

  const viteProc = spawn(
    "node",
    [
      path.resolve(WEB_DIR, "node_modules/vite/bin/vite.js"),
      "--port",
      "5173",
      "--host",
      "127.0.0.1",
    ],
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

    // 1. Open /console and run the flood
    await page.goto("http://127.0.0.1:5173/console", { waitUntil: "networkidle" });
    const runBtn = page.getByRole("button", { name: /Reset and run the flood/i });
    await runBtn.waitFor({ state: "visible", timeout: 10000 });
    await runBtn.click();

    await sleep(1500);

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
    await sleep(500);

    // 2. Open /merchant at 1440x900 (merchant-ask.png) and 360x740 (merchant-mobile.png)
    await page.goto("http://127.0.0.1:5173/merchant", { waitUntil: "networkidle" });
    const consentBtn = page.getByRole("button", {
      name: /ஆம், பதிவு செய்யுங்கள்/i,
    });
    await consentBtn.waitFor({ state: "visible", timeout: 10000 });
    await sleep(300);
    await page.screenshot({ path: MERCHANT_ASK_PNG, fullPage: false });
    console.log(`Saved screenshot to ${MERCHANT_ASK_PNG}`);

    await page.setViewportSize({ width: 360, height: 740 });
    await sleep(300);
    await page.screenshot({ path: MERCHANT_MOBILE_PNG, fullPage: false });
    console.log(`Saved screenshot to ${MERCHANT_MOBILE_PNG}`);

    // Tap consent for Selvi
    await page.setViewportSize({ width: 1440, height: 900 });
    await consentBtn.click();

    await page.waitForFunction(
      () => {
        const text = (document.body.textContent || "").toLowerCase();
        return text.includes("claim filed") && text.includes("forms filled");
      },
      { timeout: 15000 }
    );

    // 3. Open /adjuster, approve batch (7), wait for 7 refunds, capture adjuster.png
    await page.goto("http://127.0.0.1:5173/adjuster", { waitUntil: "networkidle" });
    const approveBtn = page.getByRole("button", { name: /Approve batch \(7\)/i });
    await approveBtn.waitFor({ state: "visible", timeout: 15000 });
    await approveBtn.click();

    await page.waitForFunction(
      () => {
        const text = (document.body.textContent || "").toLowerCase();
        return text.includes("7 of 7") && text.includes("batch approved (7)");
      },
      { timeout: 20000 }
    );
    await sleep(400);
    await page.screenshot({ path: ADJUSTER_PNG, fullPage: false });
    console.log(`Saved screenshot to ${ADJUSTER_PNG}`);

    // 4. Return to /console, verify 7 refund lines and 1440x900 fit, capture console.png
    await page.goto("http://127.0.0.1:5173/console", { waitUntil: "networkidle" });
    await page.waitForFunction(
      () => {
        const text = (document.body.textContent || "").toLowerCase();
        return (
          text.includes("7 processed") &&
          text.includes("batch of 7 approved") &&
          !text.includes("(0 steps)")
        );
      },
      { timeout: 15000 }
    );
    await sleep(500);

    const dimensions = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      clientHeight: document.documentElement.clientHeight,
    }));
    console.log("Console viewport check:", JSON.stringify(dimensions));
    if (dimensions.scrollHeight > 900) {
      throw new Error(
        `Console overflowed 1440x900 viewport: scrollHeight=${dimensions.scrollHeight}`
      );
    }

    await page.screenshot({ path: CONSOLE_PNG, fullPage: false });
    console.log(`Saved screenshot to ${CONSOLE_PNG}`);

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
