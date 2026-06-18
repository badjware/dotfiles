#!/usr/bin/env node
// Usage: node key.js <key> [selector]
// Presses a key, optionally focused on a selector first.
// Key examples: Enter, Tab, Escape, ArrowDown, Backspace
const { chromium } = require("playwright");

const key = process.argv[2];
const selector = process.argv[3];
if (!key) {
  console.error("Usage: key.js <key> [selector]");
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
  if (selector) {
    await page.locator(selector).press(key, { timeout: 3000 });
  } else {
    await page.keyboard.press(key);
  }
  console.log("OK");
  process.exit(0);
})().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
