# search-web extension

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that registers a `search_web` tool backed by DuckDuckGo's lite HTML endpoint (`https://lite.duckduckgo.com/lite/`). No API key needed.

[Camoufox](https://camoufox.com/) is optional. When the `camoufox` Node module can be resolved through `NODE_PATH` and its browser starts, the search page is fetched with it. The tool starts one headless browser on first use and closes it on `session_shutdown`. This browser is separate from the one in `fetch-url`. Each search uses a new browser context, waits for the `load` event, and parses the raw response body. The rendered DOM is not used, because DOM serialization changes the attribute quotes that the parser matches. The browser ignores the proxy environment variables, like the HTTP fallback does.

If Camoufox fails for any reason (module missing, browser launch failure, navigation error, timeout, HTTP status >= 300, or a page that is not a DuckDuckGo Lite results page, such as a CAPTCHA), the tool uses a plain HTTP request with Node's `node:https`.

Pairs naturally with the `fetch-url` extension: the agent uses `search_web` to find candidate pages and `fetch_url` to read the promising ones.

## Tool: `search_web`

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | required | Focused, non-empty search query, up to 500 characters. |
| `max_results` | number | `5` | Clamped to `[1, 10]`. |

Returns a numbered list of `{title, url, snippet}` entries:
- `content[0].text`: human-readable formatted list.
- `details.query`, `details.results[]` (structured form for downstream tools).

Result handling:
- DuckDuckGo redirect URLs (`/l/?uddg=...`) are unwrapped to the real target.
- Results are deduplicated by `(scheme, host, path, query)`, ignoring trailing slashes and host case.
- Only `http(s)` results with a non-empty title are kept.
- HTML tags and entities in titles/snippets are stripped/decoded.

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `PI_FETCH_USER_AGENT` | a Lynx-compatible value | `User-Agent` header sent with the HTTP fallback. Camoufox uses its own. Shared with `fetch_url`. |
| `PI_FETCH_TIMEOUT_S` | `20` | Total request deadline and socket inactivity timeout of the HTTP fallback, and the Camoufox navigation timeout, in seconds. Shared with `fetch_url`. |
| `PI_DDG_DEFAULT_MAX_RESULTS` | `5` | Default for `max_results` when the model omits it. |

## Caveats

- The parser scrapes DuckDuckGo's lite HTML and is sensitive to layout changes. If results suddenly come back empty, the regexes in `index.ts` likely need updating.
- DuckDuckGo may rate-limit aggressive use. Keep queries focused and do not send duplicate searches in parallel. The tool surfaces failures as tool errors rather than retrying.
- The tool rejects responses that do not identify themselves as DuckDuckGo Lite search pages, rather than treating them as an empty result set.
- No locale/region/safe-search controls are exposed; the lite endpoint uses defaults.
