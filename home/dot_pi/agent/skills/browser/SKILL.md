---
name: browser
description: "Control a Chrome browser: navigate pages, click elements, type text, read page content as text, and take screenshots. Use when the task requires interacting with a web page or inspecting page content."
---

# Browser Skill

Controls a persistent Chrome instance via CDP (Chrome DevTools Protocol) on `localhost:9222`.
All scripts live in the skill directory at `scripts/`.

## Setup

Run once per session (or if Chrome is not responding):

```bash
bash <skill-dir>/scripts/setup.sh
```

Verify Chrome is ready:

```bash
curl -sf http://localhost:9222/json/version | jq .
```

## Read page content

Prefer text over screenshots.

First, get the full body text:

```bash
node <skill-dir>/scripts/text.js
```

If the output is noisy or too large, inspect the page structure to find a tighter selector:

```bash
node <skill-dir>/scripts/html.js   # stripped HTML (no scripts/styles)
```

Then scope `text.js` to a specific element:

```bash
node <skill-dir>/scripts/text.js "main"
node <skill-dir>/scripts/text.js "#content"
```

Fall back to a screenshot only when visual layout matters or text extraction is insufficient:

```bash
node <skill-dir>/scripts/screenshot.js              # full page
node <skill-dir>/scripts/screenshot.js "#chart"    # specific element
```

Then use the `read` tool on `/tmp/browser-screenshot.png` to see the result.

## Navigate

```bash
node <skill-dir>/scripts/navigate.js <url>
```

## Click

Accepts any Playwright-compatible selector (CSS, text, role, etc.):

```bash
node <skill-dir>/scripts/click.js "button:has-text('Submit')"
node <skill-dir>/scripts/click.js "#login-btn"
```

## Type

Clears the field and types the given text:

```bash
node <skill-dir>/scripts/type.js "input[name='q']" "search query"
```

## Press a key

Useful for submitting forms, dismissing dialogs, navigating dropdowns:

```bash
node <skill-dir>/scripts/key.js Enter
node <skill-dir>/scripts/key.js Enter "input[name='q']"   # focused on element
node <skill-dir>/scripts/key.js Escape
node <skill-dir>/scripts/key.js Tab
```

## Evaluate JavaScript

Returns JSON-serialized result:

```bash
node <skill-dir>/scripts/eval.js "document.title"
node <skill-dir>/scripts/eval.js "document.querySelector('h1')?.textContent"
```

## Workflow pattern

1. `bash <skill-dir>/scripts/setup.sh` (if not already running)
2. `node <skill-dir>/scripts/navigate.js <url>`
3. `node <skill-dir>/scripts/text.js` to read the page; use `html.js` if you need to discover selectors
4. Act: `click.js`, `type.js`, `eval.js`
5. `text.js` again to verify the result
6. Fall back to `screenshot.js` → `read /tmp/browser-screenshot.png` only when text is not enough
7. Repeat steps 4-5 until done

## Troubleshooting

- **Connection refused**: Chrome is not running or crashed. Re-run `setup.sh`.
- **Element not found**: The selector may be wrong or the page is still loading. Try `eval.js "document.readyState"` and `html.js` to inspect the current DOM.
- **Chrome logs**: `cat /tmp/browser-skill-chrome.log`
- **Authentication required**: Stop and ask the user to log in manually.
