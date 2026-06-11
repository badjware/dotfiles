#!/usr/bin/env node
// Usage: node navigate.js <url>
const { chromium } = require("playwright");

const url = process.argv[2];
if (!url) { console.error("Usage: navigate.js <url>"); process.exit(1); }

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] ?? await ctx.newPage();
  await page.goto(url, { waitUntil: "domcontentloaded" });
  console.log("navigated to", page.url());
  await browser.close();
})();
