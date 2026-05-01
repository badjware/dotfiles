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
SERVER_NAME = "fetch-url"
SERVER_VERSION = "0.3.0"
USER_AGENT = os.environ.get("PI_DDG_USER_AGENT", "pi-fetch-url/0.3")
DEFAULT_TIMEOUT_S = float(os.environ.get("PI_DDG_TIMEOUT_S", "20"))
DEFAULT_FETCH_MAX_CHARS = int(os.environ.get("PI_DDG_DEFAULT_FETCH_MAX_CHARS", "12000"))
MAX_FETCH_BYTES = int(os.environ.get("PI_DDG_MAX_FETCH_BYTES", str(2 * 1024 * 1024)))
ALLOW_PRIVATE = os.environ.get("PI_DDG_ALLOW_PRIVATE", "0").lower() in {"1", "true", "yes", "on"}
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
    stripped = decoded.lstrip()
    if stripped.startswith("<!DOCTYPE html") or stripped.startswith("<html") or "<body" in stripped[:5000].lower():
        title, text = html_to_text(decoded)
    else:
        title, text = None, normalize_text(decoded)

    original_length = len(text)
    if original_length > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"

    summary_lines = [f"URL: {final_url}"]
    if title:
        summary_lines.append(f"Title: {title}")
    summary_lines.append("")
    summary_lines.append(text or "No readable text content extracted.")

    return make_text_result(
        "\n".join(summary_lines).strip(),
        {
            "requested_url": raw_url,
            "final_url": final_url,
            "title": title,
            "content": text,
            "truncated": original_length > max_chars,
        },
    )


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
                    }
                ]
            },
        }

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = fetch_url(arguments) if name == "fetch_url" else make_tool_error(f"Unknown tool: {name}")
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
