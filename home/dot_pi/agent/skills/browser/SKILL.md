---
name: browser
description: "Control a Chrome browser: navigate, click, type, submit forms, and read content from the live DOM (including JS-rendered or auth-gated pages). Use when the task requires interaction or when the content is only available after client-side rendering. Heavy: starts a persistent Chrome instance and requires a Wayland display (`$WAYLAND_DISPLAY` must be set)."
---

# Browser Skill

Controls a persistent Chrome instance via CDP (Chrome DevTools Protocol) on `localhost:9222`.
All scripts live in the skill directory at `scripts/`. Never chain scripts together with `&&` or `;` in the same `bash` call.

## Setup

Run **once per session**:

```bash
./scripts/setup.sh
```

If `setup.sh` exits with a non-zero code, **stop immediately** and report the error to the user. Do not proceed with any further browser commands.

Running the setup script will kill any existing chrome instance. Never run `setup.sh` more than once per session, unless the user **explicitly requests the browser to be restarted**. If a user tells you that an issue has been resolved, do not run `setup.sh` again since this will reset the browser state and revert the resolution.

**Never launch Chrome manually.** Always use `setup.sh`, even if you need to work around an issue. If `setup.sh` cannot be made to work, stop and ask the user for help.

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

Then use the `read` tool on `/tmp/browser-skill/screenshot.png` to see the result.

## Navigation

Your primary means of navigation is clicking around on the page. Use `click.js` to click elements. The script accepts any Playwright-compatible selector (CSS, text, role, etc.). The selector must match exactly one element. If it matches multiple, the script will error. Use a more specific selector to disambiguate.

Prefer role-based selectors derived from the AX tree output, as they are more reliable than text-based ones:

```bash
./scripts/click.js "role=button[name='Submit']"
./scripts/click.js "role=link[name='Grafana']"
./scripts/click.js "#login-btn"
./scripts/click.js "a:has-text('Title') >> nth=0"
```

If you need to jump to a given URL:

```bash
./scripts/navigate.js <url>
```

Prefer clicking elements on the page rather than using `navigate.js`. This is because clicking simulates interactions and allows the page to update its state accordingly (e.g. setting cookies, updating the AX tree, etc.). Use `navigate.js` only when you need to jump to a specific URL that cannot be reached via clicking (e.g. deep link).

**Always run `navigate.js` as a standalone command, never chained with `&&` or `;` after another command or before another command in the same `bash` call.** After `navigate.js` returns, verify the result with `text.js` or `ax.js` in a separate call before proceeding.

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

**Last resort only.** The user is watching the browser and wants to see the interaction happen on the page. Executing JavaScript bypasses the visible UI, so the user cannot follow what is going on. Prefer `click.js`, `type.js`, `key.js`, and `navigate.js` even when `eval.js` would be shorter or more convenient.

Do not use `eval.js` to:
- Read text or attributes (use `text.js`, `ax.js`, or `html.js`).
- Click, focus, submit, or otherwise trigger interactions (use `click.js` / `key.js`).
- Set input values (use `type.js`).
- Scroll, hover, or navigate (use the corresponding scripts, or click a real element).

Only acceptable uses are things with no UI equivalent, for example extracting a value from a non-visible DOM node for debugging, extracting structured data like JSON, or probing `window.__STATE__` when the page exposes no other affordance. Before using it, ask the user for explicit permission and briefly justify why no interaction-based script would work.

```bash
./scripts/eval.js "document.title"
./scripts/eval.js "document.querySelector('h1')?.textContent"
```

## Typical workflow pattern

1. `./scripts/setup.sh` (if not already running).
2. `./scripts/navigate.js <url>` for the initial landing page.
3. `./scripts/text.js` to read the page; `./scripts/ax.js` to discover selectors. Do not take a screenshot to verify the result of an action.
4. Act: `click.js`, `type.js`, `key.js`.
5. Repeat steps 3-4 until done.

## Cleanup

To kill Chrome and wipe all browsing state (cookies, cache, login sessions):

```bash
./scripts/cleanup.sh
```

Only run this at the request of the user.

## Troubleshooting

- Chrome logs are at `/tmp/browser-skill/chrome.log`
- **Element not found / timeout**: Re-run `ax.js` to get a fresh view of the DOM and derive a new selector from it.
- **Strict mode violation (resolved to N elements)**: The selector matched more than one element. Use a more specific selector (e.g.: append `>> nth=0` to target the first match).
- If you encounter one of the following, stop and ask the user to resolve it manually:
  - Captcha
  - Login prompt
  - 2FA prompt
  - HTTP auth challenge, or proxy authentication issue (eg: `ERR_INVALID_AUTH_CREDENTIALS`)
  - SSL or other security issue
