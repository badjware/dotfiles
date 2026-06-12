#!/usr/bin/env node
// Usage: node click.js <selector>
const { chromium } = require("playwright");

const selector = process.argv[2];
if (!selector) {
  console.error("Usage: click.js <selector>");
  process.exit(1);
}

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) {
    console.error("no open page");
    process.exit(1);
  }
  await page.locator(selector).click({ timeout: 10000 });
  console.log("OK");
  process.exit(0);
})().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
