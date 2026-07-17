#!/usr/bin/env node
// Persistent background script started by setup.sh.
// Emits gentle mouse movement and occasional scroll on pages while they are
// loading, then idles. Any scroll it performs is reversed once 'load' fires
// so the page comes to rest at its natural position.
// Disable with BROWSER_SKILL_HUMANIZER=0.
const { chromium } = require("./browser-lib");

if (process.env.BROWSER_SKILL_HUMANIZER === "0") {
  process.exit(0);
}

const rand = (min, max) => min + Math.random() * (max - min);
const randInt = (min, max) => Math.floor(rand(min, max + 1));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const GRACE_MS = parseInt(process.env.BROWSER_SKILL_HUMANIZER_GRACE_MS || "4000", 10);
const LOADING_BUDGET_MS = 60000; // upper bound while waiting for 'load'

const state = new Map(); // page -> { activeUntil, scrollDy }

function attach(page) {
  if (state.has(page)) return;
  state.set(page, { activeUntil: Date.now() + LOADING_BUDGET_MS, scrollDy: 0 });

  page.on("request", (req) => {
    if (!req.isNavigationRequest()) return;
    if (req.frame() !== page.mainFrame()) return;
    const s = state.get(page);
    if (s) s.activeUntil = Date.now() + LOADING_BUDGET_MS;
  });

  page.on("load", () => {
    const s = state.get(page);
    if (!s) return;
    s.activeUntil = Date.now() + GRACE_MS;
  });

  page.on("close", () => state.delete(page));
}

async function tick(page, s) {
  const size = page.viewportSize() || (await page
    .evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }))
    .catch(() => null));
  if (!size) return;

  const hidden = await page.evaluate(() => document.hidden).catch(() => true);
  if (hidden) return;

  const margin = 20;
  const tx = randInt(margin, Math.max(margin + 1, size.width - margin));
  const ty = randInt(margin, Math.max(margin + 1, size.height - margin));
  await page.mouse.move(tx, ty, { steps: randInt(10, 30) });

  if (Math.random() < 0.2) {
    const dy = randInt(-120, 120);
    await page.mouse.wheel(0, dy);
    s.scrollDy += dy;
  }
}

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222", { timeout: 15000 });
  const ctx = browser.contexts()[0];

  ctx.on("page", attach);
  for (const p of ctx.pages()) attach(p);

  // eslint-disable-next-line no-constant-condition
  while (true) {
    await sleep(randInt(200, 600));
    const now = Date.now();
    for (const [page, s] of state) {
      if (page.isClosed()) { state.delete(page); continue; }
      if (now < s.activeUntil) {
        await tick(page, s).catch(() => {});
      } else if (s.scrollDy !== 0) {
        const dy = -s.scrollDy;
        s.scrollDy = 0;
        try { await page.mouse.wheel(0, dy); } catch {}
      }
    }
  }
})().catch((err) => {
  console.error("humanizer:", err.message);
  process.exit(1);
});
