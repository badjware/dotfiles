# DuckDuckGo MCP bridge for pi

This global pi extension adds two tools:

- `search_web` — search DuckDuckGo via the Lite endpoint
- `fetch_url` — fetch a public web page and extract readable text

## Installed paths

- Extension: `~/.pi/agent/extensions/ddg-mcp-bridge/`
- Python server: `~/.pi/agent/extensions/ddg-mcp-bridge/ddg_mcp_server.py`

In this environment that resolves to:

- `/.pi/agent/extensions/ddg-mcp-bridge/`

## How it works

pi does not ship with built-in MCP support, so this extension acts as the bridge:

1. pi loads `index.ts`
2. the extension starts the Python server over stdio
3. the extension talks to the server using MCP-style JSON-RPC messages
4. pi exposes `search_web` and `fetch_url` as normal tools to the model

## Activate it

If pi is already running:

```text
/reload
```

Or just start a new pi session.

## Optional commands

- `/ddg-status` — check whether the bridge starts correctly
- `/ddg-restart` — restart the bridge process

## Optional environment variables

- `PI_DDG_MCP_PYTHON` — Python executable to use, default: `python3`
- `PI_DDG_MCP_TIMEOUT_MS` — MCP request timeout in milliseconds, default: `30000`
- `PI_DDG_TIMEOUT_S` — network timeout for DuckDuckGo/page fetches, default: `20`
- `PI_DDG_DEFAULT_MAX_RESULTS` — default `search_web` result count, default: `5`
- `PI_DDG_DEFAULT_FETCH_MAX_CHARS` — default `fetch_url` max chars, default: `12000`
- `PI_DDG_MAX_FETCH_BYTES` — max bytes downloaded per page, default: `2097152`
- `PI_DDG_USER_AGENT` — custom HTTP user-agent
- `PI_DDG_ALLOW_PRIVATE=1` — allow fetching private/local addresses (disabled by default)

## Security default

`fetch_url` only allows public `http` and `https` targets by default. It blocks localhost and private/reserved IP ranges unless you explicitly set:

```bash
export PI_DDG_ALLOW_PRIVATE=1
```

## Notes

- Search uses DuckDuckGo Lite HTML results rather than an official full-search API.
- If DuckDuckGo changes its Lite markup, `search_web` may need a parser update.
