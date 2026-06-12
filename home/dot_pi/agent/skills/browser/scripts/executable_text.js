#!/usr/bin/env node
// Usage: node text.js [selector]
// Extracts visible text from the page (or a specific element).
const { chromium } = require("playwright");

const selector = process.argv[2] ?? "body";

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) {
    console.error("no open page");
    process.exit(1);
  }
  const text = await page.locator(selector).innerText({ timeout: 10000 });
  console.log(text);
  process.exit(0);
})().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
