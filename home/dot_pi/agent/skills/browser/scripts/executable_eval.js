#!/usr/bin/env node
// Usage: node eval.js <js-expression>
const { chromium } = require("playwright");

const expr = process.argv[2];
if (!expr) { console.error("Usage: eval.js <js-expression>"); process.exit(1); }

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  if (!page) { console.error("no open page"); process.exit(1); }
  const result = await page.evaluate(expr);
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})();
