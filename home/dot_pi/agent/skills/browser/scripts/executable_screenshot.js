#!/usr/bin/env node
// Usage: node screenshot.js [selector]
const { chromium } = require("playwright");

const selector = process.argv[2];
const out = "/tmp/browser-screenshot.png";

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) { console.error("no open page"); process.exit(1); }
  if (selector) {
    await page.locator(selector).screenshot({ path: out, timeout: 10000 });
  } else {
    await page.screenshot({ path: out, fullPage: false });
  }
  console.log(out);
  await browser.close();
})();
