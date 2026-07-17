#!/usr/bin/env node
// Usage: node navigate.js <url>
const { chromium } = require("./browser-lib");

const url = process.argv[2];
if (!url) {
  console.error("Usage: navigate.js <url>");
  process.exit(1);
}

(async () => {
  const browser = await chromium.connectOverCDP("http://localhost:9222", { timeout: 15000 });
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] ?? (await ctx.newPage());
  // Navigate by setting window.location directly from within the page context.
  // This produces the same Sec-Fetch-* / Upgrade-Insecure-Requests headers as a
  // real user navigation, unlike CDP's Page.navigate command which some sites
  // (e.g. Reddit) detect and block server-side.
  const currentUrl = page.url();
  let timedOut = false;
  if (currentUrl === "about:blank" || currentUrl === "") {
    // Can't use location.href from about:blank; fall back to CDP navigate.
    await page.goto(url, { waitUntil: "load" }).catch((err) => {
      if (/timeout/i.test(err.message)) timedOut = true;
      else throw err;
    });
  } else {
    await Promise.all([
      page.waitForNavigation({ waitUntil: "load" }).catch((err) => {
        if (/timeout/i.test(err.message)) timedOut = true;
        else throw err;
      }),
      page.evaluate((u) => { window.location.href = u; }, url),
    ]);
  }

  // A load timeout usually means a user-interaction prompt (proxy auth, 2FA,
  // etc.) is blocking the page. Stop here so the user can complete it.
  if (timedOut) {
    console.error("Navigation timed out waiting for page load. A prompt may require user interaction (proxy auth, login, 2FA, etc.). Please complete it, then re-run this command.");
    process.exit(1);
  }

  // Anti-bot interstitials (Reddit JS challenge, Cloudflare, etc.) load a
  // stub page that resolves a token and replaces the document in place.
  // Poll both title and body until the challenge clears.
  const challengeRe = /just a moment|checking your browser|attention required|blocked by network security|you've been blocked/i;
  const looksLikeChallenge = async () => {
    const title = await page.title().catch(() => "");
    const body = await page.evaluate(() => document.body?.innerText ?? "").catch(() => "");
    return /[?&](js_challenge=1|__cf_chl_)/.test(page.url()) || challengeRe.test(title) || challengeRe.test(body);
  };
  if (await looksLikeChallenge()) {
    await page
      .waitForFunction(
        (re) => {
          const t = document.title + " " + (document.body?.innerText ?? "");
          return !new RegExp(re, "i").test(t);
        },
        challengeRe.source,
        { timeout: 15000, polling: 500 }
      )
      .catch(() => {});
  }

  console.log("OK");
  process.exit(0);
})().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
