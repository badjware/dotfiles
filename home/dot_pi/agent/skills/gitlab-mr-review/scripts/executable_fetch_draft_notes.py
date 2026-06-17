#!/usr/bin/env python3
"""
Fetch the current user's draft notes on a GitLab MR.

Usage: fetch_draft_notes.py <mr-url>
  e.g. fetch_draft_notes.py https://gitlab.com/mygroup/myproject/-/merge_requests/42

Output: JSON to stdout with keys: draft_notes, discussions
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

HTTP_TIMEOUT = 30
PER_PAGE = 100
USER_AGENT = "gitlab-mr-review"


# ---------------------------------------------------------------------------
# Auth (mirrors fetch_mr.py)
# ---------------------------------------------------------------------------

def _resolve_auth(url_host: str) -> tuple[str, str]:
    host = url_host or os.environ.get("GITLAB_HOST") or "gitlab.com"
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        print(
            "ERROR: No GitLab token found. Set GITLAB_TOKEN env var.",
            file=sys.stderr,
        )
        sys.exit(2)
    return host, token


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _api(host: str, token: str, path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"https://{host}/api/v4{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"PRIVATE-TOKEN": token, "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(
                f"ERROR: GitLab returned {e.code} for {path}. "
                "Check that your token is valid and has the `read_api` scope.",
                file=sys.stderr,
            )
            sys.exit(3)
        raise


def _api_paged(host: str, token: str, path: str, params: dict[str, Any] | None = None) -> list[Any]:
    out: list[Any] = []
    page = 1
    while True:
        p = dict(params or {})
        p.update({"per_page": PER_PAGE, "page": page})
        chunk = _api(host, token, path, p)
        if not isinstance(chunk, list) or not chunk:
            break
        out.extend(chunk)
        if len(chunk) < PER_PAGE:
            break
        page += 1
    return out


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def parse_mr_url(url: str) -> tuple[str, str, int]:
    m = re.match(r"https?://([^/]+)/(.+?)/-/merge_requests/(\d+)", url)
    if not m:
        print(f"ERROR: Cannot parse MR URL: {url}", file=sys.stderr)
        sys.exit(1)
    return m.group(1), m.group(2), int(m.group(3))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: fetch_draft_notes.py <mr-url>", file=sys.stderr)
        sys.exit(1)

    url_host, project_path, mr_iid = parse_mr_url(sys.argv[1])
    host, token = _resolve_auth(url_host)

    project_id = urllib.parse.quote(project_path, safe="")
    notes_raw = _api_paged(host, token, f"/projects/{project_id}/merge_requests/{mr_iid}/draft_notes")
    discussions_raw = _api_paged(host, token, f"/projects/{project_id}/merge_requests/{mr_iid}/discussions")

    notes = []
    for n in notes_raw:
        position = n.get("position")
        notes.append({
            "id": n["id"],
            "note": n["note"],
            "resolve_discussion": n.get("resolve_discussion", False),
            "file": position.get("new_path") if position else None,
            "line": position.get("new_line") if position else None,
        })

    discussions = []
    for disc in discussions_raw:
        thread_notes = [n for n in disc.get("notes", []) if not n.get("system", False)]
        if not thread_notes:
            continue
        first = thread_notes[0]
        position = first.get("position")
        resolvable = first.get("resolvable", False)
        discussions.append({
            "id": disc["id"],
            "resolvable": resolvable,
            "resolved": first.get("resolved", False) if resolvable else None,
            "file": position.get("new_path") if position else None,
            "line": position.get("new_line") if position else None,
            "notes": [
                {"author": n["author"]["name"], "body": n["body"]}
                for n in thread_notes
            ],
        })

    result: dict[str, Any] = {"draft_notes": notes, "discussions": discussions}
    if not notes:
        result["message"] = "No draft notes found for this MR."

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
