#!/usr/bin/env python3
import gzip
import html
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ddg-mcp-server"
SERVER_VERSION = "0.1.0"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
USER_AGENT = os.environ.get("PI_DDG_USER_AGENT", "pi-ddg-mcp/0.1")
DEFAULT_TIMEOUT_S = float(os.environ.get("PI_DDG_TIMEOUT_S", "20"))
DEFAULT_MAX_RESULTS = int(os.environ.get("PI_DDG_DEFAULT_MAX_RESULTS", "5"))
DEFAULT_FETCH_MAX_CHARS = int(os.environ.get("PI_DDG_DEFAULT_FETCH_MAX_CHARS", "12000"))
MAX_FETCH_BYTES = int(os.environ.get("PI_DDG_MAX_FETCH_BYTES", str(2 * 1024 * 1024)))
ALLOW_PRIVATE = os.environ.get("PI_DDG_ALLOW_PRIVATE", "0").lower() in {"1", "true", "yes", "on"}
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
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"[ \t\x0b\x0c\r]+")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "main",
    "header",
    "footer",
    "nav",
    "aside",
    "ul",
    "ol",
    "li",
    "table",
    "tr",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
}


class PublicUrlError(ValueError):
    pass


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._suppress_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "head"}:
            self._suppress_depth += 1
            return
        if self._suppress_depth > 0:
            return
        if tag == "br" or tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "head"}:
            self._suppress_depth = max(0, self._suppress_depth - 1)
            return
        if self._suppress_depth > 0:
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._suppress_depth > 0:
            return
        if data:
            self.parts.append(data)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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


def normalize_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    lines = []
    for raw_line in value.splitlines():
        line = WHITESPACE_RE.sub(" ", raw_line).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    normalized = "\n".join(lines)
    return MULTI_NEWLINE_RE.sub("\n\n", normalized).strip()


def parse_search_results(html_text: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in RESULT_RE.finditer(html_text):
        url = unwrap_ddg_url(match.group("href"))
        title = strip_tags(match.group("title"))
        snippet = strip_tags(match.group("snippet") or "")
        display = strip_tags(match.group("display") or "")
        if not url.startswith(("http://", "https://")):
            continue
        if not title:
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


def validate_public_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise PublicUrlError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise PublicUrlError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise PublicUrlError("Embedded credentials in URLs are not allowed.")
    hostname = parsed.hostname
    if ALLOW_PRIVATE:
        return parsed
    if hostname.lower() == "localhost":
        raise PublicUrlError("Localhost URLs are blocked.")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as error:
        raise PublicUrlError(f"Could not resolve hostname: {hostname}") from error
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise PublicUrlError(f"Blocked non-public address: {hostname} -> {ip}")
    return parsed


def build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(SafeRedirectHandler())


def fetch_bytes(url: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> tuple[str, bytes, str | None]:
    validate_public_url(url)
    opener = build_opener()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.1",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with opener.open(request, timeout=timeout_s) as response:
        final_url = response.geturl()
        validate_public_url(final_url)
        body = response.read(MAX_FETCH_BYTES + 1)
        if len(body) > MAX_FETCH_BYTES:
            body = body[:MAX_FETCH_BYTES]
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "deflate":
            body = zlib.decompress(body)
        charset = response.headers.get_content_charset() or "utf-8"
        return final_url, body, charset


def html_to_text(html_text: str) -> tuple[str | None, str]:
    title_match = TITLE_RE.search(html_text)
    title = strip_tags(title_match.group(1)) if title_match else None
    cleaned = SCRIPT_STYLE_RE.sub(" ", html_text)
    extractor = TextExtractor()
    extractor.feed(cleaned)
    extractor.close()
    text = normalize_text("".join(extractor.parts))
    return title, text


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


def fetch_url(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_url = str(arguments.get("url", "")).strip()
    if not raw_url:
        return make_tool_error("fetch_url requires a non-empty url.")

    max_chars = int(arguments.get("max_chars") or DEFAULT_FETCH_MAX_CHARS)
    max_chars = max(500, min(100000, max_chars))

    try:
        final_url, body, charset = fetch_bytes(raw_url)
    except PublicUrlError as error:
        return make_tool_error(str(error))

    decoded = body.decode(charset or "utf-8", "replace")
    title: str | None
    text: str
    stripped = decoded.lstrip()
    if stripped.startswith("<!DOCTYPE html") or stripped.startswith("<html") or "<body" in stripped[:5000].lower():
        title, text = html_to_text(decoded)
    else:
        title = None
        text = normalize_text(decoded)

    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"

    summary_lines = [f"URL: {final_url}"]
    if title:
        summary_lines.append(f"Title: {title}")
    summary_lines.append("")
    summary_lines.append(text or "No readable text content extracted.")

    structured = {
        "requested_url": raw_url,
        "final_url": final_url,
        "title": title,
        "content": text,
        "truncated": len(text) >= max_chars,
    }
    return make_text_result("\n".join(summary_lines).strip(), structured)


TOOLS = [
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
    },
    {
        "name": "fetch_url",
        "description": "Fetch a public web page and extract readable text content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public http or https URL to fetch"},
                "max_chars": {
                    "type": "number",
                    "description": "Maximum number of extracted characters to return (default 12000)",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
]


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
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "search_web":
                result = search_web(arguments)
            elif name == "fetch_url":
                result = fetch_url(arguments)
            else:
                result = make_tool_error(f"Unknown tool: {name}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as error:  # noqa: BLE001
            log(f"Tool failure ({name}): {error}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": make_tool_error(f"Tool execution failed: {error}"),
            }

    if request_id is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
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
