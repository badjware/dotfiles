# search-web extension

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that registers a `search_web` tool backed by DuckDuckGo's lite HTML endpoint (`https://lite.duckduckgo.com/lite/`). No API key needed.

Pairs naturally with the `fetch-url` extension: the agent uses `search_web` to find candidate pages and `fetch_url` to read the promising ones.

## Tool: `search_web`

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | required | Non-empty search query. |
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
| `PI_DDG_USER_AGENT` | `pi-search-web/0.5` | `User-Agent` header sent with the request. |
| `PI_DDG_TIMEOUT_S` | `20` | Per-request timeout (seconds). |
| `PI_DDG_DEFAULT_MAX_RESULTS` | `5` | Default for `max_results` when the model omits it. |

## Caveats

- The parser scrapes DuckDuckGo's lite HTML and is sensitive to layout changes. If results suddenly come back empty, the regexes in `index.ts` likely need updating.
- DuckDuckGo may rate-limit aggressive use. The tool surfaces these as a tool error rather than retrying.
- No locale/region/safe-search controls are exposed; the lite endpoint uses defaults.
