#!/usr/bin/env node
// Persistent background script started by setup.sh.
// Auto-dismisses any JS dialog (alert/confirm/prompt) so they never block CDP.
const { chromium } = require("./browser-lib");

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222", { timeout: 15000 });
  const ctx = browser.contexts()[0];
  ctx.on("dialog", async (dialog) => {
    await dialog.dismiss();
  });
  await new Promise(() => {}); // keep alive for the session
})().catch((err) => {
  console.error("dialog-handler:", err.message);
  process.exit(1);
});
