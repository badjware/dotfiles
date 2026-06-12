#!/usr/bin/env node
// Usage: node ax.js
// Returns the page accessibility tree as JSON, for selector discovery.
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) {
    console.error("no open page");
    process.exit(1);
  }
  const snapshot = await page.ariaSnapshot();
  console.log(snapshot);
  process.exit(0);
})().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
