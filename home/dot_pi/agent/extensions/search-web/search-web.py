#!/usr/bin/env python3
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "search-web"
SERVER_VERSION = "0.3.0"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
USER_AGENT = os.environ.get("PI_DDG_USER_AGENT", "pi-search-web/0.3")
DEFAULT_TIMEOUT_S = float(os.environ.get("PI_DDG_TIMEOUT_S", "20"))
DEFAULT_MAX_RESULTS = int(os.environ.get("PI_DDG_DEFAULT_MAX_RESULTS", "5"))
SAFE_SEARCH_MAP = {
    "off": "-2",
    "moderate": "-1",
    "strict": "1",
}
RESULT_RE = re.compile(
    r"<a rel=\"nofollow\" href=\"(?P<href>[^\"]+)\" class='result-link'>(?P<title>.*?)</a>"
    r"(?P<tail>.*?)"
    r"(?:<td class='result-snippet'>\s*(?P<snippet>.*?)\s*</td>)?"
    r"(?P<tail2>.*?)"
    r"<span class='link-text'>(?P<display>.*?)</span>",
    re.S,
)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"[ \t\x0b\x0c\r]+")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def send_message(message: dict[str, Any]) -> None:
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("ascii", "replace").strip()
        if not decoded:
            break
        if ":" not in decoded:
            continue
        key, value = decoded.split(":", 1)
        headers[key.lower()] = value.strip()

    content_length = headers.get("content-length")
    if not content_length:
        raise ValueError("Missing Content-Length header")

    length = int(content_length)
    body = sys.stdin.buffer.read(length)
    if len(body) != length:
        raise EOFError("Unexpected EOF while reading message body")
    return json.loads(body.decode("utf-8"))


def make_text_result(text: str, structured_content: Any) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured_content,
        "isError": False,
    }


def make_tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def strip_tags(value: str) -> str:
    text = TAG_RE.sub("", value)
    text = html.unescape(text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def unwrap_ddg_url(href: str) -> str:
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
        query = urllib.parse.parse_qs(parsed.query)
        uddg = query.get("uddg")
        if uddg:
            return urllib.parse.unquote(uddg[0])
    return href


def parse_search_results(html_text: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in RESULT_RE.finditer(html_text):
        url = unwrap_ddg_url(match.group("href"))
        title = strip_tags(match.group("title"))
        snippet = strip_tags(match.group("snippet") or "")
        display = strip_tags(match.group("display") or "")
        if not url.startswith(("http://", "https://")) or not title:
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "display_url": display or url,
                "snippet": snippet,
            }
        )
        if len(results) >= max_results:
            break
    return results


def format_search_results(query: str, results: list[dict[str, str]]) -> str:
    if not results:
        return f"No DuckDuckGo results found for: {query}"
    lines = [f"DuckDuckGo results for: {query}", ""]
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result['title']}")
        lines.append(f"   URL: {result['url']}")
        if result.get("snippet"):
            lines.append(f"   Snippet: {result['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()


def search_web(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query", "")).strip()
    if not query:
        return make_tool_error("search_web requires a non-empty query.")

    max_results = int(arguments.get("max_results") or DEFAULT_MAX_RESULTS)
    max_results = max(1, min(10, max_results))
    region = str(arguments.get("region") or "").strip()
    safe_search = str(arguments.get("safe_search") or "moderate").strip().lower()

    params = {"q": query}
    if region:
        params["kl"] = region
    if safe_search in SAFE_SEARCH_MAP:
        params["kp"] = SAFE_SEARCH_MAP[safe_search]

    url = DDG_LITE_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_S) as response:
        html_text = response.read().decode("utf-8", "replace")

    results = parse_search_results(html_text, max_results)
    structured = {
        "query": query,
        "region": region or None,
        "safe_search": safe_search,
        "results": results,
    }
    return make_text_result(format_search_results(query, results), structured)


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "search_web",
                        "description": "Search DuckDuckGo and return ranked results with titles, URLs, and snippets.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "max_results": {
                                    "type": "number",
                                    "description": "Maximum number of results to return (default 5, max 10)",
                                },
                                "region": {
                                    "type": "string",
                                    "description": "DuckDuckGo region code like us-en or uk-en",
                                },
                                "safe_search": {
                                    "type": "string",
                                    "description": "Safe search mode: off, moderate, or strict",
                                },
                            },
                            "required": ["query"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        }

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = search_web(arguments) if name == "search_web" else make_tool_error(f"Unknown tool: {name}")
        except Exception as error:  # noqa: BLE001
            log(f"Tool failure ({name}): {error}")
            result = make_tool_error(f"Tool execution failed: {error}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    if request_id is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    while True:
        try:
            message = read_message()
        except Exception as error:  # noqa: BLE001
            log(f"Protocol error: {error}")
            return 1
        if message is None:
            return 0
        response = handle_request(message)
        if response is not None:
            send_message(response)


if __name__ == "__main__":
    raise SystemExit(main())
