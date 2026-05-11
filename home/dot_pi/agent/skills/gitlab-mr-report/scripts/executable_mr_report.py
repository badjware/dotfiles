#!/usr/bin/env python3
"""
Generate a report of GitLab merge requests where the current user is
either the author or a reviewer, flagging areas that need attention.

Auth resolution order:
  1. GITLAB_TOKEN env var
  2. ~/.config/glab-cli/config.yml (token for the configured host)

Host resolution order:
  1. GITLAB_HOST env var (e.g. "gitlab.example.com")
  2. glab config "host"
  3. "gitlab.com"
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STALE_DAYS = 7
HTTP_TIMEOUT = 30
PER_PAGE = 100
MAX_WORKERS = 8
USER_AGENT = "gitlab-mr-report"

# Pipeline statuses treated as "failing" in both the attention bucket and the
# snapshot table. Keep these two renderings in sync by reading from one place.
_BAD_PIPELINE_STATUSES = frozenset({"failed", "canceled"})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _read_glab_config() -> tuple[str | None, str | None]:
    """Return (host, token) from glab config if available.

    Handles the subset of YAML glab produces:

        host: gitlab.com
        hosts:
          gitlab.com:
            token: xxx
    """
    cfg = Path.home() / ".config" / "glab-cli" / "config.yml"
    if not cfg.exists():
        return None, None

    top_host: str | None = None
    hosts: dict[str, str] = {}
    try:
        lines = cfg.read_text().splitlines()
        current_host: str | None = None
        in_hosts = False
        for raw in lines:
            if raw.startswith("host:"):
                top_host = raw.split(":", 1)[1].strip().strip('"') or None
                continue
            if raw.rstrip() == "hosts:":
                in_hosts = True
                continue
            if not in_hosts:
                continue
            if raw and not raw.startswith(" "):
                in_hosts = False
                continue
            stripped = raw.strip()
            if raw.startswith("  ") and not raw.startswith("    ") and stripped.endswith(":"):
                current_host = stripped[:-1].strip()
            elif stripped.startswith("token:") and current_host:
                hosts[current_host] = stripped.split(":", 1)[1].strip().strip('"')
    except OSError:
        return None, None

    # Prefer top-level host; otherwise fall back to the single host entry.
    host = top_host or (next(iter(hosts)) if len(hosts) == 1 else None)
    token = hosts.get(host) if host else None
    return host, token


def _resolve_auth() -> tuple[str, str]:
    env_host = os.environ.get("GITLAB_HOST")
    env_token = os.environ.get("GITLAB_TOKEN")
    glab_host, glab_token = _read_glab_config()
    host = env_host or glab_host or "gitlab.com"
    token = env_token or glab_token
    if not token:
        print(
            "ERROR: No GitLab token found. Set GITLAB_TOKEN or run `glab auth login`.",
            file=sys.stderr,
        )
        sys.exit(2)
    return host, token


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _api(
    host: str,
    token: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:
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


def _api_paged(
    host: str,
    token: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> list[Any]:
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
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _mr_ref(mr: dict) -> str:
    refs = mr.get("references") or {}
    return refs.get("full") or f"!{mr['iid']}"


def _count_discussion_threads(
    host: str,
    token: str,
    mr: dict,
    my_id: int,
) -> tuple[int, int]:
    """Return (waiting_on_me, commented_awaiting).

    waiting_on_me:  unresolved threads where I participated (or authored the
                    MR) and the last note is not from me.
    commented_awaiting: unresolved threads where I actually wrote a note and the
                    last note IS from me — i.e. I'm waiting on someone else
                    to respond or resolve.
    """
    try:
        discussions = _api_paged(
            host,
            token,
            f"/projects/{mr['project_id']}/merge_requests/{mr['iid']}/discussions",
        )
    except urllib.error.URLError:
        return 0, 0

    i_am_author = (mr.get("author") or {}).get("id") == my_id
    waiting_on_me = 0
    commented_awaiting = 0
    for d in discussions:
        notes = [n for n in d.get("notes", []) if not n.get("system")]
        if not notes:
            continue
        # Skip fully resolved resolvable threads.
        resolvable_notes = [n for n in notes if n.get("resolvable")]
        if resolvable_notes and all(n.get("resolved") for n in resolvable_notes):
            continue
        participants = {n["author"]["id"] for n in notes}
        i_wrote_note = my_id in participants
        last_is_me = notes[-1]["author"]["id"] == my_id
        # waiting_on_me: I participated (or authored MR) and last note not mine
        if (i_am_author or i_wrote_note) and not last_is_me:
            waiting_on_me += 1
        # commented_awaiting: I actually wrote a note and last note IS mine
        if i_wrote_note and last_is_me:
            commented_awaiting += 1
    return waiting_on_me, commented_awaiting


def _count_diff_lines(diff: str) -> tuple[int, int]:
    added = removed = 0
    for ln in diff.split("\n"):
        if ln.startswith("+") and not ln.startswith("+++"):
            added += 1
        elif ln.startswith("-") and not ln.startswith("---"):
            removed += 1
    return added, removed


# ---------------------------------------------------------------------------
# Per-MR data gathering
# ---------------------------------------------------------------------------

@dataclass
class MRRow:
    ref: str
    url: str
    title: str
    roles: list[str]
    age_days: int | None
    updated: datetime | None
    draft: bool
    conflict: bool
    pipeline: str | None
    waiting: int
    commented_awaiting: int
    files: int
    added: int
    removed: int
    approvals_got: int
    approvals_required: int
    approved_by_me: bool

    @property
    def pipeline_bad(self) -> bool:
        return self.pipeline in _BAD_PIPELINE_STATUSES

    @property
    def role_str(self) -> str:
        return "/".join(self.roles) if self.roles else ""


def _fetch_mr_row(
    host: str,
    token: str,
    mr: dict,
    roles: list[str],
    my_id: int,
    now: datetime,
) -> MRRow:
    project_id = mr["project_id"]
    iid = mr["iid"]

    # Detail endpoint fills in head_pipeline + authoritative has_conflicts.
    try:
        detail = _api(host, token, f"/projects/{project_id}/merge_requests/{iid}") or {}
    except urllib.error.URLError:
        detail = {}
    merged = {**mr, **detail}

    updated = _parse_iso(merged.get("updated_at"))
    pipeline = (
        (merged.get("head_pipeline") or {}).get("status")
        or (merged.get("pipeline") or {}).get("status")
    )
    if pipeline is None:
        try:
            pipes = _api(
                host, token, f"/projects/{project_id}/merge_requests/{iid}/pipelines"
            )
            if isinstance(pipes, list) and pipes:
                pipeline = pipes[0].get("status")
        except urllib.error.URLError:
            pass

    # Diff size — /diffs is paginated (GitLab 14.7+); fall back to the
    # older /changes endpoint (which silently truncates at 100 files).
    files = added = removed = 0
    try:
        diffs = _api_paged(
            host, token,
            f"/projects/{project_id}/merge_requests/{iid}/diffs",
        )
        files = len(diffs)
        for c in diffs:
            a, r = _count_diff_lines(c.get("diff") or "")
            added += a
            removed += r
    except urllib.error.URLError:
        try:
            ch = _api(host, token, f"/projects/{project_id}/merge_requests/{iid}/changes")
            ch_list = (ch or {}).get("changes") or []
            files = len(ch_list)
            for c in ch_list:
                a, r = _count_diff_lines(c.get("diff") or "")
                added += a
                removed += r
        except urllib.error.URLError:
            pass

    # Approvals
    approvals_got = approvals_required = 0
    approved_by_me = False
    try:
        appr = _api(host, token, f"/projects/{project_id}/merge_requests/{iid}/approvals") or {}
        approved_by = appr.get("approved_by") or []
        approvals_got = len(approved_by)
        approvals_required = appr.get("approvals_required") or 0
        approved_by_me = any(
            ((entry.get("user") or {}).get("id")) == my_id for entry in approved_by
        )
    except urllib.error.URLError:
        pass

    waiting, commented_awaiting = _count_discussion_threads(host, token, merged, my_id)

    return MRRow(
        ref=_mr_ref(mr),
        url=mr["web_url"],
        title=mr["title"],
        roles=roles,
        age_days=(now - updated).days if updated else None,
        updated=updated,
        draft=bool(merged.get("draft") or merged.get("work_in_progress")),
        conflict=bool(merged.get("has_conflicts")),
        pipeline=pipeline,
        waiting=waiting,
        commented_awaiting=commented_awaiting,
        files=files,
        added=added,
        removed=removed,
        approvals_got=approvals_got,
        approvals_required=approvals_required,
        approved_by_me=approved_by_me,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _link(row: MRRow) -> str:
    return f"[{row.ref}]({row.url})"


def _age_str(row: MRRow) -> str:
    return f"{row.age_days}d" if row.age_days is not None else "?"


def _approvals_cell(r: MRRow) -> str:
    if r.approvals_required:
        cell = f"{r.approvals_got}/{r.approvals_required}"
        return f"✅ {cell}" if r.approvals_got >= r.approvals_required else cell
    if r.approvals_got:
        return f"{r.approvals_got}/–"
    return "—"


def _pipeline_cell(r: MRRow) -> str:
    status = r.pipeline
    if status is None:
        return "—"
    if status == "success":
        return "✅ success"
    if status in _BAD_PIPELINE_STATUSES:
        return f"❌ {status}"
    if status == "running":
        return "🟡 running"
    return status


def _render_snapshot(rows: list[MRRow]) -> list[str]:
    out = [
        "## 📋 Snapshot",
        "_Per-MR overview; approvals and pipeline reflect the author's POV. "
        "A ✅ next to your role means **you** have approved this MR._",
        "",
        "| MR | Title | Draft | Role | Approvals | Pipeline | Conflicts | Files | +/- | Age |",
        "|---|---|---|---|---|---|---|---:|---:|---|",
    ]
    for r in rows:
        title = (r.title or "").replace("|", "\\|")
        role_cell = r.role_str or "—"
        if r.approved_by_me:
            role_cell = f"{role_cell} ✅" if r.role_str else "✅"
        out.append(
            f"| {_link(r)} | {title} | {'📝' if r.draft else '—'} | {role_cell} | {_approvals_cell(r)} | "
            f"{_pipeline_cell(r)} | {'❌ conflicts' if r.conflict else '✅ clean'} | "
            f"{r.files} | +{r.added}/-{r.removed} | {_age_str(r)} |"
        )
    out.append("")
    return out


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def _sort_key_quickest(r: MRRow) -> tuple[int, int]:
    """Default Focus sort: fewest files first, then smallest diff."""
    return (r.files, r.added + r.removed)


def _effective_required(r: MRRow) -> int:
    return r.approvals_required if r.approvals_required > 0 else 1


def build_focus(rows: list[MRRow]) -> dict[str, list]:
    """Precompute Focus category membership.

    The rules here are the authoritative implementation of the inclusion
    rules documented in SKILL.md's Focus template. The skill tells the LLM
    to render each category from these lists in order — it must not
    re-derive membership from the raw ``mrs`` array.

    Each list is already sorted per its category's sort rule (default:
    ``files`` ↑ then ``added+removed`` ↑). Most categories emit a flat list
    of ``ref`` strings; categories that carry an extra per-entry label
    (currently only ``needs_rebase``) emit dicts.
    """
    stale = STALE_DAYS

    def refs(pred, *, key=_sort_key_quickest) -> list[str]:
        return [r.ref for r in sorted([x for x in rows if pred(x)], key=key)]

    merge_ready = refs(
        lambda r: "author" in r.roles
        and r.approvals_got >= _effective_required(r)
        and r.pipeline == "success"
        and not r.conflict
        and not r.draft
    )

    review_queue = refs(
        lambda r: "reviewer" in r.roles
        and "author" not in r.roles
        and not r.draft
        and not r.approved_by_me
        and r.commented_awaiting == 0
    )

    authored_conversations_waiting = refs(
        lambda r: "author" in r.roles and r.waiting > 0
    )

    reviewing_replies_waiting = refs(
        lambda r: "reviewer" in r.roles and r.waiting > 0
    )

    commented_awaiting_response = refs(
        lambda r: r.commented_awaiting > 0
    )

    # needs_rebase: author AND (conflicts OR stale-but-mergeable-clean)
    needs_rebase_rows = []
    for r in rows:
        if "author" not in r.roles:
            continue
        if r.conflict:
            needs_rebase_rows.append((r, "conflicts"))
        elif (
            (r.age_days or 0) >= stale
            and r.approvals_got >= _effective_required(r)
            and r.pipeline == "success"
            and not r.draft
        ):
            needs_rebase_rows.append((r, "ready-needs-merging"))
    needs_rebase_rows.sort(key=lambda pair: _sort_key_quickest(pair[0]))
    needs_rebase = [{"ref": r.ref, "reason": reason} for r, reason in needs_rebase_rows]

    awaiting_approvals = refs(
        lambda r: "author" in r.roles
        and not r.conflict
        and (r.age_days or 0) >= stale
        and r.approvals_got < _effective_required(r)
    )

    candidates_to_close = refs(
        lambda r: "author" in r.roles
        and (
            (r.age_days or 0) > 365
            or ((r.age_days or 0) > 90 and r.conflict)
        )
    )

    return {
        "merge_ready": merge_ready,
        "review_queue": review_queue,
        "authored_conversations_waiting": authored_conversations_waiting,
        "reviewing_replies_waiting": reviewing_replies_waiting,
        "commented_awaiting_response": commented_awaiting_response,
        "needs_rebase": needs_rebase,
        "awaiting_approvals": awaiting_approvals,
        "candidates_to_close": candidates_to_close,
    }


def _render_data_footer(rows: list[MRRow]) -> list[str]:
    """Emit a machine-readable JSON block with every MRRow field.

    The Focus section (see SKILL.md) is generated from this block rather
    than re-parsed from the prose above, so new MRRow fields or Focus
    categories can't silently drift out of sync with what's rendered.
    """
    payload = []
    for r in rows:
        payload.append({
            "ref": r.ref,
            "url": r.url,
            "title": r.title,
            "roles": r.roles,
            "age_days": r.age_days,
            "updated": r.updated.isoformat() if r.updated else None,
            "draft": r.draft,
            "conflict": r.conflict,
            "pipeline": r.pipeline,
            "pipeline_bad": r.pipeline_bad,
            "waiting": r.waiting,
            "commented_awaiting": r.commented_awaiting,
            "files": r.files,
            "added": r.added,
            "removed": r.removed,
            "approvals_got": r.approvals_got,
            "approvals_required": r.approvals_required,
            "approved_by_me": r.approved_by_me,
        })
    focus = build_focus(rows)
    return [
        "## 🧩 Data (for Focus generation)",
        "",
        "_Machine-readable snapshot of every MR, plus precomputed Focus"
        r" category membership. The skill's Focus section must be rendered"
        r" by iterating `focus.<category>` in the given order and looking up"
        r" each `ref` in `mrs`; do not re-derive membership._",
        "",
        "```json",
        json.dumps(
            {"stale_days": STALE_DAYS, "focus": focus, "mrs": payload},
            indent=2,
        ),
        "```",
        "",
    ]


def _is_archived(host: str, token: str, pid: int) -> bool:
    try:
        proj = _api(host, token, f"/projects/{pid}")
    except urllib.error.URLError:
        return False
    return bool(proj.get("archived"))


def _archived_project_ids(host: str, token: str, project_ids: set[int]) -> set[int]:
    """Return the subset of project_ids whose projects are archived.

    GitLab has no bulk "projects by ID" endpoint, so we fan out one request
    per project. The calls are independent, so we run them in a small thread
    pool to keep total latency bounded.
    """
    if not project_ids:
        return set()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        flags = ex.map(lambda pid: (pid, _is_archived(host, token, pid)), project_ids)
        return {pid for pid, archived in flags if archived}


def _collect_mrs(
    host: str, token: str, my_username: str
) -> tuple[list[dict], dict[int, list[str]], int]:
    """Fetch authored + reviewer MRs, dedupe, tag roles, drop archived.

    Returns ``(mrs, roles_by_id, archived_dropped)`` where ``archived_dropped``
    is the number of MRs hidden because they live in archived projects.
    """
    authored = _api_paged(
        host, token, "/merge_requests",
        {"state": "opened", "scope": "created_by_me"},
    )
    reviewing = _api_paged(
        host, token, "/merge_requests",
        # scope=all is required; the default (created_by_me) would filter
        # out every MR not authored by us.
        {"state": "opened", "scope": "all", "reviewer_username": my_username},
    )
    by_id: dict[int, dict] = {}
    roles: dict[int, set[str]] = {}
    for mr in authored:
        by_id[mr["id"]] = mr
        roles.setdefault(mr["id"], set()).add("author")
    for mr in reviewing:
        by_id.setdefault(mr["id"], mr)
        roles.setdefault(mr["id"], set()).add("reviewer")

    # Filter out MRs from archived projects.
    project_ids = {mr["project_id"] for mr in by_id.values()}
    archived = _archived_project_ids(host, token, project_ids)
    dropped = 0
    if archived:
        before = len(by_id)
        by_id = {k: v for k, v in by_id.items() if v["project_id"] not in archived}
        roles = {k: v for k, v in roles.items() if k in by_id}
        dropped = before - len(by_id)

    sorted_roles = {k: sorted(v) for k, v in roles.items()}
    return list(by_id.values()), sorted_roles, dropped


def build_report() -> str:
    host, token = _resolve_auth()
    me = _api(host, token, "/user")
    my_id: int = me["id"]
    my_username: str = me["username"]

    mrs, roles_by_id, archived_dropped = _collect_mrs(host, token, my_username)
    now = datetime.now(timezone.utc)

    lines: list[str] = [
        f"# Merge Request Report for @{my_username}",
        f"_Host: {host} — Generated: {now.isoformat(timespec='seconds')} — Stale threshold: {STALE_DAYS}d_",
        "",
    ]
    n_author = sum(1 for r in roles_by_id.values() if "author" in r)
    n_reviewer = sum(1 for r in roles_by_id.values() if "reviewer" in r)
    summary = (
        f"**{len(mrs)} open MR(s)** — {n_author} authored, {n_reviewer} as reviewer "
        f"(overlap is counted in both)."
    )
    if archived_dropped:
        summary += (
            f" _({archived_dropped} MR(s) from archived projects hidden.)_"
        )
    lines.append(summary)
    lines.append("")

    if not mrs:
        return "\n".join(lines)

    # Per-MR enrichment issues ~5 independent HTTP calls; fan out across MRs
    # in a thread pool. Order doesn't matter here — we re-sort by age below.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        rows = list(ex.map(
            lambda mr: _fetch_mr_row(
                host, token, mr, roles_by_id[mr["id"]], my_id, now,
            ),
            mrs,
        ))
    rows.sort(key=lambda r: r.age_days if r.age_days is not None else -1, reverse=True)

    lines.extend(_render_snapshot(rows))
    lines.extend(_render_data_footer(rows))
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_report())
