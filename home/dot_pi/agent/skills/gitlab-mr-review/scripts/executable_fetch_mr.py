#!/usr/bin/env python3
"""
Fetch GitLab MR data for review: metadata, full diffs, and discussions.

Usage: fetch_mr.py <mr-url>
  e.g. fetch_mr.py https://gitlab.com/mygroup/myproject/-/merge_requests/42

Auth resolution order:
  1. GITLAB_TOKEN env var (GITLAB_HOST for the host)
  2. ~/.config/glab-cli/config.yml

Output: JSON to stdout with keys: mr, changes
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

HTTP_TIMEOUT = 60
PER_PAGE = 100
USER_AGENT = "gitlab-mr-review"


# ---------------------------------------------------------------------------
# Auth
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
    """Return (host, project_path, mr_iid) from an MR web URL."""
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
        print("Usage: fetch_mr.py <mr-url>", file=sys.stderr)
        sys.exit(1)

    url_host, project_path, mr_iid = parse_mr_url(sys.argv[1])
    host, token = _resolve_auth(url_host)

    project_id = urllib.parse.quote(project_path, safe="")
    base = f"/projects/{project_id}/merge_requests/{mr_iid}"

    # Fetch MR metadata
    mr = _api(host, token, base)

    # Fetch diffs — /changes returns everything in one shot but is paginated
    # in newer GitLab versions via the diffs endpoint
    changes_raw = _api_paged(host, token, f"{base}/diffs")

    # --- Build output ---

    result: dict[str, Any] = {
        "mr": {
            "title": mr["title"],
            "description": mr.get("description") or "",
            "source_branch": mr["source_branch"],
            "target_branch": mr["target_branch"],
        },
        "changes": [],
    }

    # Changes: skip binaries, keep full diff
    skipped_binary: list[str] = []
    for ch in changes_raw:
        if ch.get("diff") is None or (ch.get("diff") == "" and not ch.get("new_file") and not ch.get("deleted_file")):
            # Likely a binary or empty diff — skip
            path = ch.get("new_path") or ch.get("old_path") or "unknown"
            skipped_binary.append(path)
            continue
        result["changes"].append({
            "old_path": ch.get("old_path"),
            "new_path": ch.get("new_path"),
            "new_file": ch.get("new_file", False),
            "deleted_file": ch.get("deleted_file", False),
            "renamed_file": ch.get("renamed_file", False),
            "diff": ch.get("diff", ""),
        })

    if skipped_binary:
        result["skipped_binary_files"] = skipped_binary

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
