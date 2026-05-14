# fetch-url extension

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that registers a `fetch_url` tool which retrieves a public web page and returns its readable text content (via the `lynx` text browser).

## Requirements

`lynx` must be installed and on `PATH`:

```bash
# Debian/Ubuntu
apt install lynx
```

## Tool: `fetch_url`

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `url` | string | required | Must be `http://` or `https://`. |
| `max_chars` | number | `32000` | Clamped to `[500, 100000]`. Output is truncated with a trailing `…` if exceeded. |
| `include_links` | boolean | `false` | When true, appends lynx's numbered link list at the end of the page text. Useful when the agent intends to follow links. |

The tool returns:
- `content[0].text`: a header (`URL: ...`) plus the cleaned page text.
- `details.requested_url`, `details.content`, `details.truncated`, `details.original_length`.

Cleanup applied to lynx's output:
- normalised line endings
- stripped `(BUTTON)` markers and long underscore separators
- collapsed runs of 3+ blank lines to 2

## Configuration

Tunables (all optional, read from `process.env` at load time):

| Env var | Default | Effect |
|---|---|---|
| `PI_FETCH_TIMEOUT_S` | `20` | Connect/read timeout passed to lynx (seconds). |
| `PI_FETCH_WIDTH` | `1024` | `-width` flag passed to lynx (controls wrapping). |
| `PI_FETCH_DEFAULT_MAX_CHARS` | `32000` | Default for `max_chars` when the model omits it. |
