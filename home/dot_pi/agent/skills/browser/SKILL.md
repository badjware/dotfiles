---
name: browser
description: "Control a Chrome browser: navigate, click, type, submit forms, and read content from the live DOM (including JS-rendered or auth-gated pages). Use when the task requires interaction or when the content is only available after client-side rendering. Heavy: starts a persistent Chrome instance and requires a Wayland display (`$WAYLAND_DISPLAY` must be set)."
---

# Browser Skill

Controls a persistent Chrome instance via CDP (Chrome DevTools Protocol) on `localhost:9222`.
All scripts live in the skill directory at `scripts/`.

## Setup

Run once per session (or if Chrome is not responding):

```bash
./scripts/setup.sh
```

Running the setup script will kill any existing chrome instance, so never run it in the middle of a task unless you encounter issues.

## Selector discovery

Once on a page, you can discover selectors for elements of interest using the Accessibility Tree:

```bash
./scripts/ax.js     # accessibility tree (compact, semantic, visibility-aware)
```

The AX tree only includes visible, interactable elements and exposes their role, name, and state (e.g. `expanded: false`). Use it as the default for selector discovery. If a collapsed element shows `expanded: false`, look for a toggler or expand button and click it first if you need to interact with it.

Fall back to `html.js` only when the AX tree lacks enough detail (e.g. two elements with the same name that need disambiguation by CSS class or ID).

## Read page content

**Never take a screenshot unless the user explicitly asks for one, or the task is inherently visual (e.g. inspecting a chart or image).** Do not use screenshots to verify navigation, check page state, or read text.

Always use a selector if possible to limit the scope of what you read. Use `ax.js` to discover selectors.

Use `text.js` to read page content:

```bash
./scripts/text.js "body"
./scripts/text.js "#content"
./scripts/text.js        # entire visible text
```

Screenshots are a last resort:

```bash
./scripts/screenshot.js              # full page
./scripts/screenshot.js "#chart"    # specific element
```

Then use the `read` tool on `/tmp/browser-screenshot.png` to see the result.

## Navigation

Your primary means of navigation is clicking around on the page. Use `click.js` to click elements. The script accepts any Playwright-compatible selector (CSS, text, role, etc.). The selector must match exactly one element. If it matches multiple, the script will error. Use a more specific selector to disambiguate:

```bash
./scripts/click.js "button:has-text('Submit')"
./scripts/click.js "#login-btn"
./scripts/click.js "a:has-text('Title') >> nth=0"
```

If you need to jump to a given URL:

```bash
./scripts/navigate.js <url>
```

Prefer clicking elements on the page rather than using `navigate.js`. This is because clicking simulates interactions and allows the page to update its state accordingly (e.g. setting cookies, updating the AX tree, etc.). Use `navigate.js` only when you need to jump to a specific URL that cannot be reached via clicking (e.g. deep link).

## Keyboard interactions

To clear a field and type the given text:

```bash
./scripts/type.js "input[name='q']" "search query"
```

To press a key:

```bash
./scripts/key.js Enter
./scripts/key.js Enter "input[name='q']"   # focused on element
./scripts/key.js Escape
./scripts/key.js Tab
```

Useful for submitting forms, dismissing dialogs, navigating dropdowns, etc.

## Evaluate JavaScript

Returns a JSON-serialized result:

```bash
./scripts/eval.js "document.title"
./scripts/eval.js "document.querySelector('h1')?.textContent"
```

This must only be used as a last resort when other commands are insufficient.

## Typical workflow pattern

1. `./scripts/setup.sh` (if not already running).
2. `./scripts/navigate.js <url>` for the initial landing page.
3. `./scripts/text.js` to read the page; `./scripts/ax.js` to discover selectors. Do not take a screenshot to verify the result of an action.
4. Act: `click.js`, `type.js`, `key.js`.
5. Repeat steps 3-4 until done.

## Troubleshooting

- **Connection refused**: Chrome is not running or crashed. Offer to the user to either investigate the crash or to run `./scripts/setup.sh` to start a new instance.
  - Chrome logs are at `/tmp/browser-skill-chrome.log`
- **Element not found**: The selector may be wrong or the page is still loading. Try `eval.js "document.readyState"` and/or `ax.js` to inspect the current DOM.
- **Strict mode violation (resolved to N elements)**: The selector matched more than one element. Use a more specific selector (e.g.: append `>> nth=0` to target the first match).
- **User intervention required**: If you encounter one of the following, stop and ask the user to resolve it manually:
  - Captcha
  - Login prompt
  - 2FA prompt
  - SSL or other security issue
