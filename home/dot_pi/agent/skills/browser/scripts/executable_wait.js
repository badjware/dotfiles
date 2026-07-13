#!/usr/bin/env node
// Usage: node wait.js [timeout_seconds]
const { chromium } = require("patchright");

const timeoutSec = process.argv[2] ? Number(process.argv[2]) : 5;
if (Number.isNaN(timeoutSec) || timeoutSec <= 0) {
  console.error("Usage: wait.js [timeout_seconds]");
  process.exit(1);
}

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222", { timeout: 15000 });
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) {
    console.error("no open page");
    process.exit(1);
  }
  await page.waitForLoadState("networkidle", { timeout: timeoutSec * 1000 });
  console.log("OK");
  process.exit(0);
})().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
