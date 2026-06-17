# fetch-url extension

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that registers a `fetch_url` tool which retrieves a web page and returns its readable text content as Markdown, using [trafilatura](https://trafilatura.readthedocs.io/) for main-content extraction. Not suitable for structured data (e.g. API responses); use `bash` with `curl` for that.

## Requirements

`trafilatura` must be installed and on `PATH`:

```bash
pipx install trafilatura
```

## Tool: `fetch_url`

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `url` | string | required | URL to fetch. |
| `include_links` | boolean | `false` | Keep inline `[text](url)` hyperlinks in the extracted Markdown. Useful when the agent intends to follow links. |

Output is truncated to pi's standard tool limits (`DEFAULT_MAX_LINES` lines or `DEFAULT_MAX_BYTES`, whichever is hit first). When truncated, the full extracted Markdown is written to a unique temp file and its path is reported back to the LLM in the truncation notice.

The tool returns:
- `content[0].text`: the extracted Markdown, with a truncation notice appended if applicable.
- `details.requested_url`, `details.truncated`, plus `details.truncation` and `details.fullOutputPath` when truncated.

The HTTP fetch is performed via Node's stdlib (`node:https` / `node:http`, with manual redirect following, configurable timeout, Lynx UA), then the HTML is piped to `trafilatura --output-format markdown --formatting` over stdin. Trafilatura drops navigation, sidebars, footers, comments and ads.

## Configuration

Tunables (all optional, read from `process.env` at load time):

| Env var | Default | Effect |
|---|---|---|
| `PI_FETCH_TIMEOUT_S` | `20` | Idle timeout for the HTTP request (seconds). |
| `AGENT_USER_AGENT` | current Lynx UA | `User-Agent` header sent with the HTTP fetch. Defaults to a real-world Lynx UA so the tool identifies honestly as a text browser. |
