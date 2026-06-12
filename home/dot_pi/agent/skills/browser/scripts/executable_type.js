#!/usr/bin/env node
// Usage: node type.js <selector> <text>
const { chromium } = require("playwright");

const selector = process.argv[2];
const text = process.argv[3];
if (!selector || text === undefined) {
  console.error("Usage: type.js <selector> <text>");
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
  await page.locator(selector).fill(text, { timeout: 10000 });
  console.log("typed into", selector);
  process.exit(0);
})();
