#!/usr/bin/env node
// Usage: node html.js
// Returns the page HTML stripped of script/style tags, for selector discovery.
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) { console.error("no open page"); process.exit(1); }
  const html = await page.evaluate(() => {
    const clone = document.documentElement.cloneNode(true);
    clone.querySelectorAll("script, style, svg, noscript").forEach(el => el.remove());
    return clone.outerHTML;
  });
  console.log(html);
  await browser.close();
})();
