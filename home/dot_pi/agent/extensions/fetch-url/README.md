# fetch-url extension

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that registers a `fetch_url` tool which retrieves a web page and returns its readable text content (via the `lynx` text browser). Not suitable for structured data (e.g. API responses); use `bash` with `curl` for that.

## Requirements

`lynx` must be installed and on `PATH`:

```bash
# Debian/Ubuntu
apt install lynx
```

## Tool: `fetch_url`

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `url` | string | required | URL to fetch (any scheme `lynx` supports). |
| `max_chars` | number | `32000` | Clamped to `[500, 100000]`. Output is truncated with a trailing `…` if exceeded. |
| `include_links` | boolean | `false` | When true, appends lynx's numbered link list at the end of the page text. Useful when the agent intends to follow links. |
| `strip_chrome` | boolean | `true` | When true, removes leading/trailing blocks of short lines (navigation menus, footers) from the output. Set to false if content appears unexpectedly truncated or the page layout is unconventional. |

The tool returns:
- `content[0].text`: the cleaned page text.
- `details.requested_url`, `details.content`, `details.truncated`, `details.original_length`.

Cleanup applied to lynx's output:
- normalised line endings
- `#word…` lines stripped (lynx renders `<link>` and `<a name>` elements as these; never real content)
- `(BUTTON)` markers stripped (`<button>` / `<input type="button">`)
- `[ ]` / `[X]` checkbox markers stripped (`<input type="checkbox">`)
- `[INLINE]` / `[IMG]` placeholders stripped (`<img>` tags with no alt text)
- long underscore sequences stripped (`<input type="text">`)
- collapsed runs of 3+ blank lines to 2
- (when `strip_chrome=true`) leading and trailing blank-line-separated blocks that contain no line ≥ `PI_FETCH_LONG_LINE_THRESHOLD` chars are dropped; blocks with at least one long line are considered content and anchor the kept region. **Known limitation**: long URLs or legal notices in footers may extend the kept region slightly into footer territory.

## Configuration

Tunables (all optional, read from `process.env` at load time):

| Env var | Default | Effect |
|---|---|---|
| `PI_FETCH_TIMEOUT_S` | `20` | Connect/read timeout passed to lynx (seconds). |
| `PI_FETCH_WIDTH` | `1024` | `-width` flag passed to lynx (controls wrapping). |
| `PI_FETCH_DEFAULT_MAX_CHARS` | `32000` | Default for `max_chars` when the model omits it. |
| `PI_FETCH_LONG_LINE_THRESHOLD` | `60` | Minimum line length (chars) for a block to be considered content by the chrome-stripping heuristic. |
