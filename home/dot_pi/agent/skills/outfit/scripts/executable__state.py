"""Shared helpers for outfit scripts. Stdlib only."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

# State machine for task status. The lead requests transitions; we validate.
TASK_STATUSES = {"todo", "in_progress", "in_review", "done", "blocked", "cancelled"}
TERMINAL_STATUSES = {"done", "cancelled"}
# blocked and cancelled are reachable from any non-terminal state (including todo).
TASK_TRANSITIONS: dict[str, set[str]] = {
    "todo": {"in_progress", "blocked", "cancelled"},
    "in_progress": {"in_review", "blocked", "cancelled"},
    "in_review": {"done", "in_progress", "blocked", "cancelled"},
    "blocked": {"todo", "in_progress", "cancelled"},
    "done": set(),  # terminal
    "cancelled": set(),  # terminal
}

# Current state schema version. Bumped whenever the on-disk shape of status.json,
# tasks.json, or the .plan/ layout changes in a way migrate.py must reconcile.
# Legacy projects predating versioning are treated as version 1.
#   v2: schema_version stamp + issue registry (issues.json)
#   v3: linked-project handoff registry (linked.json)
CURRENT_SCHEMA_VERSION = 3

# Issue registry (issues.json). Replaces stale deferred-issues.md scanning.
ISSUE_STATUSES = {"open", "resolved", "accepted", "superseded"}

# Linked-project handoffs (linked.json). Release state of a cross-repository
# prerequisite the current project depends on.
LINK_RELEASE_STATUSES = {"pending", "released"}
ISSUE_SEVERITIES = {
    "blocker",
    "major",
    "minor-defect",
    "optional-enhancement",
    "observation",
}

PHASES = {"discovery", "planning", "execution"}
# Phase transition guards.
# `execution` is reachable only via approve-gate-1, not set-phase.
# `planning` is reachable from `discovery` only via approve-discovery, not set-phase.
# `discovery` is reachable from any phase: it is also the way to revisit requirements
# mid-project.
PHASE_TRANSITIONS: dict[str, set[str]] = {
    "discovery": set(),  # use approve-discovery to advance to planning
    "planning": {"discovery"},
    "execution": {"discovery"},
}

ID_TASK_RE = re.compile(r"^T-\d{3,}$")
ID_STORY_RE = re.compile(r"^S-\d{3,}$")
ID_MILESTONE_RE = re.compile(r"^M-\d{3,}$")
ID_ISSUE_RE = re.compile(r"^I-\d{3,}$")
ID_LINK_RE = re.compile(r"^L-\d{3,}$")
CONVENTIONAL_TYPE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
CONVENTIONAL_SCOPE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
CONVENTIONAL_COMMIT_RE = re.compile(
    r"^[a-z][a-z0-9-]*(?:\([a-z0-9][a-z0-9._/-]*\))?: [^\r\n]+$"
)
PLAN_EXCLUDE_BLOCK = "# outfit local planning state\n.plan/\n"


# T-010: machine-readable error categories. Read-only usage mistakes are
# recoverable (correct and retry); state-changing and commit/staging errors are
# fatal and must be escalated; worker failures are inspected then escalated.
ERROR_EXIT_CODES = {"usage": 2, "state": 1, "commit": 3, "worker": 4}

# T-007: consecutive failed attempts on one issue before the lead must escalate.
REWORK_ATTEMPT_LIMIT = 3


def die(msg: str, category: str = "usage", code: int | None = None) -> None:
    """Emit a categorized error and exit. Category drives the exit code so callers
    can distinguish recoverable usage mistakes from fatal state/commit errors."""
    print(f"error[{category}]: {msg}", file=sys.stderr)
    sys.exit(code if code is not None else ERROR_EXIT_CODES.get(category, 1))


def parse_worker_status(path: Path) -> tuple[str | None, str]:
    """Return (status, reason) from a status-<role>.md file.

    The first non-empty line is the status word; remaining lines are the reason.
    Returns (None, "") if the file is absent.
    """
    if not path.exists():
        return None, ""
    lines = path.read_text().splitlines()
    status = None
    reason_lines: list[str] = []
    for line in lines:
        if status is None:
            if line.strip():
                status = line.strip().split()[0]
        else:
            reason_lines.append(line)
    return status, "\n".join(reason_lines).strip()


def find_plan_dir(start: Path | None = None) -> Path:
    """Walk up from cwd to find .plan/. Error if not found."""
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        cand = d / ".plan"
        if cand.is_dir():
            repo_root = cand.parent
            if git_is_repo(repo_root):
                try:
                    if git_plan_is_tracked(repo_root):
                        die(
                            ".plan/ is tracked by git from an older Outfit run; "
                            "migrate it before resuming (Outfit will not rewrite history)"
                        )
                    ensure_plan_locally_excluded(repo_root)
                except GitError as e:
                    die(str(e))
            return cand
    die("no .plan/ directory found from cwd; run scripts/plan-init.py first")


@contextlib.contextmanager
def plan_lock(plan: Path) -> Iterator[None]:
    """Serialize read-modify-write sequences so concurrent invocations cannot
    allocate duplicate IDs or clobber each other's writes."""
    lock_path = plan / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path) -> Any:
    if not path.exists():
        die(f"{path} not found")
    try:
        with path.open() as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")


def read_tasks(plan: Path) -> dict:
    data = read_json(plan / "tasks.json")
    if (
        not isinstance(data, dict)
        or "tasks" not in data
        or not isinstance(data["tasks"], list)
    ):
        die('tasks.json malformed: expected {"tasks": [...]}')
    return data


def write_tasks(plan: Path, data: dict) -> None:
    atomic_write_json(plan / "tasks.json", data)


def status_schema_version(s: dict) -> int:
    """Schema version of a status dict; legacy projects predating versioning are 1."""
    v = s.get("schema_version", 1)
    if not isinstance(v, int) or v < 1:
        die(f"status.json has invalid schema_version: {v!r}")
    return v


def check_schema_supported(s: dict) -> None:
    """Fail safely on state written by a newer Outfit than this one."""
    v = status_schema_version(s)
    if v > CURRENT_SCHEMA_VERSION:
        die(
            f"state schema_version {v} is newer than this Outfit supports "
            f"({CURRENT_SCHEMA_VERSION}); upgrade Outfit before continuing"
        )


def read_status(plan: Path) -> dict:
    data = read_json(plan / "status.json")
    if not isinstance(data, dict):
        die("status.json malformed")
    check_schema_supported(data)
    return data


def write_status(plan: Path, data: dict) -> None:
    atomic_write_json(plan / "status.json", data)


def task_by_id(tasks: list[dict], task_id: str) -> dict | None:
    for t in tasks:
        if t.get("id") == task_id:
            return t
    return None


def validate_task_shape(t: dict) -> None:
    """Validate task structure: id formats, required fields, types."""
    required = {
        "id",
        "story_id",
        "milestone",
        "title",
        "description",
        "acceptance",
        "status",
        "depends_on",
        "commit_type",
    }
    missing = required - t.keys()
    if missing:
        die(f"task missing fields: {sorted(missing)}")
    if not ID_TASK_RE.match(t["id"]):
        die(f"task id must match T-\\d{{3,}}: {t['id']!r}")
    if not ID_STORY_RE.match(t["story_id"]):
        die(f"story_id must match S-\\d{{3,}}: {t['story_id']!r}")
    if not ID_MILESTONE_RE.match(t["milestone"]):
        die(f"milestone must match M-\\d{{3,}}: {t['milestone']!r}")
    if not isinstance(t["title"], str) or not t["title"]:
        die("title must be non-empty string")
    if not isinstance(t["description"], str):
        die("description must be string")
    if not isinstance(t["acceptance"], list) or not t["acceptance"]:
        die("acceptance must be non-empty list")
    for a in t["acceptance"]:
        if not isinstance(a, str) or not a:
            die("each acceptance item must be non-empty string")
    if t["status"] not in TASK_STATUSES:
        die(f"status must be one of {sorted(TASK_STATUSES)}: {t['status']!r}")
    if not isinstance(t["depends_on"], list):
        die("depends_on must be list")
    for d in t["depends_on"]:
        if not isinstance(d, str) or not ID_TASK_RE.match(d):
            die(f"depends_on entries must match T-\\d{{3,}}: {d!r}")
    validate_commit_parts(t["commit_type"], t["title"], t.get("commit_scope"))


def check_acyclic(tasks: list[dict], new_task: dict | None = None) -> None:
    """DFS cycle check. If new_task given, validate as-if it were already in the list."""
    by_id = {t["id"]: t for t in tasks}
    if new_task is not None:
        by_id[new_task["id"]] = new_task
    color: dict[str, int] = {}  # 0=white, 1=gray, 2=black

    def visit(node: str, path: list[str]) -> None:
        c = color.get(node, 0)
        if c == 1:
            cycle = path[path.index(node) :] + [node]
            die(f"dependency cycle: {' -> '.join(cycle)}")
        if c == 2:
            return
        color[node] = 1
        for dep in by_id[node]["depends_on"]:
            if dep not in by_id:
                die(f"task {node} depends on unknown task {dep}")
            visit(dep, path + [node])
        color[node] = 2

    for tid in by_id:
        visit(tid, [])


def make_slug(text: str, max_len: int = 40) -> str:
    """Convert text to a lowercase hyphenated slug, at most max_len chars."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s


def make_work_dir_name(task_id: str, title: str) -> str:
    """Create a work directory name with slug, e.g. T-007-implement-login."""
    slug = make_slug(title)
    if slug:
        return f"{task_id}-{slug}"
    return task_id


def work_dir_for_task(plan: Path, task_id: str) -> Path:
    """Find the work directory for a task, handling slug-based names.

    Scans for `<task_id>-*/` first (created by dispatch with a slug), then
    falls back to the plain `<task_id>/` directory.
    """
    work_base = plan / "work"
    if work_base.is_dir():
        candidates = sorted(work_base.glob(f"{task_id}-*/"))
        if candidates:
            return candidates[0]
    return work_base / task_id


def next_task_id(tasks: list[dict]) -> str:
    nums = [int(t["id"].split("-")[1]) for t in tasks if ID_TASK_RE.match(t["id"])]
    n = (max(nums) + 1) if nums else 1
    return f"T-{n:03d}"


# --- issue registry helpers ---


def read_issues(plan: Path) -> dict:
    """Read issues.json, tolerating its absence on freshly-migrated projects."""
    path = plan / "issues.json"
    if not path.exists():
        return {"issues": []}
    data = read_json(path)
    if (
        not isinstance(data, dict)
        or "issues" not in data
        or not isinstance(data["issues"], list)
    ):
        die('issues.json malformed: expected {"issues": [...]}')
    return data


def write_issues(plan: Path, data: dict) -> None:
    atomic_write_json(plan / "issues.json", data)


def issue_by_id(issues: list[dict], issue_id: str) -> dict | None:
    for i in issues:
        if i.get("id") == issue_id:
            return i
    return None


def next_issue_id(issues: list[dict]) -> str:
    nums = [int(i["id"].split("-")[1]) for i in issues if ID_ISSUE_RE.match(i["id"])]
    n = (max(nums) + 1) if nums else 1
    return f"I-{n:03d}"


# --- multi-repository workspace helpers ---


def read_workspace(plan: Path) -> dict | None:
    """Read workspace.json, or None for a single-repository project.

    Absence means the classic single-repo layout: the project root is the only
    repository, so existing projects behave unchanged.
    """
    path = plan / "workspace.json"
    if not path.exists():
        return None
    data = read_json(path)
    if (
        not isinstance(data, dict)
        or "repositories" not in data
        or not isinstance(data["repositories"], dict)
        or not data["repositories"]
    ):
        die('workspace.json malformed: expected {"repositories": {name: {"path": ...}}}')
    for name, spec in data["repositories"].items():
        if not isinstance(spec, dict) or "path" not in spec:
            die(f"workspace repository {name!r} must have a path")
    return data


def write_workspace(plan: Path, data: dict) -> None:
    atomic_write_json(plan / "workspace.json", data)


def primary_repo_name(ws: dict) -> str:
    """Name of the repository at path '.', which hosts .plan/."""
    for name, spec in ws["repositories"].items():
        if spec["path"] in (".", "./"):
            return name
    die("workspace has no primary repository (path '.')", category="state")


def workspace_repo_path(plan: Path, ws: dict, name: str) -> Path:
    spec = ws["repositories"].get(name)
    if spec is None:
        die(f"unknown workspace repository {name!r}")
    return (plan.parent / spec["path"]).resolve()


def resolve_task_repo(plan: Path, task: dict) -> tuple[str | None, Path, bool]:
    """Return (repo_name, repo_path, is_primary) for a task.

    Single-repo projects (no workspace) return (None, project_root, True).
    """
    ws = read_workspace(plan)
    if ws is None:
        return None, plan.parent, True
    name = task.get("repository") or primary_repo_name(ws)
    if name not in ws["repositories"]:
        die(f"task {task.get('id')} declares unknown repository {name!r}", category="state")
    return name, workspace_repo_path(plan, ws, name), name == primary_repo_name(ws)


def repo_dirty(repo_root: Path, exclude_plan: bool) -> bool:
    """Dirty check. The primary repo excludes .plan/; secondary repos do not."""
    if exclude_plan:
        return git_working_tree_dirty(repo_root)
    r = git_run(["status", "--porcelain", "--untracked-files=all"], repo_root)
    if r.returncode != 0:
        raise GitError(f"git status failed: {r.stderr.strip()}")
    return bool(r.stdout.strip())


# --- linked-project registry helpers ---


def read_links(plan: Path) -> dict:
    """Read linked.json, tolerating its absence on projects with no linked repos."""
    path = plan / "linked.json"
    if not path.exists():
        return {"links": []}
    data = read_json(path)
    if (
        not isinstance(data, dict)
        or "links" not in data
        or not isinstance(data["links"], list)
    ):
        die('linked.json malformed: expected {"links": [...]}')
    return data


def write_links(plan: Path, data: dict) -> None:
    atomic_write_json(plan / "linked.json", data)


def link_by_id(links: list[dict], link_id: str) -> dict | None:
    for link in links:
        if link.get("id") == link_id:
            return link
    return None


def next_link_id(links: list[dict]) -> str:
    nums = [int(link["id"].split("-")[1]) for link in links if ID_LINK_RE.match(link["id"])]
    n = (max(nums) + 1) if nums else 1
    return f"L-{n:03d}"


# --- review cycle helpers ---


def latest_review_cycle(work_dir: Path) -> int:
    """Highest existing review cycle number in a task work dir, or 0 if none.

    Cycles are recorded as review-NN.md so later rework never overwrites a
    prior reviewer's output.
    """
    if not work_dir.is_dir():
        return 0
    nums = []
    for p in work_dir.glob("review-*.md"):
        m = re.fullmatch(r"review-(\d+)", p.stem)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def skill_dir() -> Path:
    """Return the outfit skill directory (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


# --- git helpers ---


class GitError(Exception):
    pass


def git_run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def git_is_repo(path: Path) -> bool:
    r = git_run(["rev-parse", "--is-inside-work-tree"], path)
    return r.returncode == 0 and r.stdout.strip() == "true"


def git_head_sha(repo_root: Path) -> str | None:
    r = git_run(["rev-parse", "HEAD"], repo_root)
    if r.returncode != 0:
        return None  # no commits yet
    return r.stdout.strip()


def git_is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    """True if `ancestor` is an ancestor of (or equal to) `descendant`."""
    r = git_run(["merge-base", "--is-ancestor", ancestor, descendant], repo_root)
    return r.returncode == 0


def git_working_tree_dirty(repo_root: Path) -> bool:
    """True if project files outside .plan/ have uncommitted changes."""
    r = git_run(
        [
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            ".",
            ":(exclude).plan",
            ":(exclude).plan/**",
        ],
        repo_root,
    )
    if r.returncode != 0:
        raise GitError(f"git status failed: {r.stderr.strip()}")
    return bool(r.stdout.strip())


def git_plan_is_tracked(repo_root: Path) -> bool:
    r = git_run(["ls-files", "--", ".plan"], repo_root)
    if r.returncode != 0:
        raise GitError(f"git ls-files failed: {r.stderr.strip()}")
    return bool(r.stdout.strip())


def ensure_plan_locally_excluded(repo_root: Path) -> None:
    """Add .plan/ to the repository-local exclude file without touching .gitignore."""
    r = git_run(["rev-parse", "--git-path", "info/exclude"], repo_root)
    if r.returncode != 0:
        raise GitError(f"could not locate git info/exclude: {r.stderr.strip()}")
    exclude = Path(r.stdout.strip())
    if not exclude.is_absolute():
        exclude = repo_root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ""
    if any(line.strip() == ".plan/" for line in existing.splitlines()):
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    separator = "" if not existing else "\n"
    exclude.write_text(existing + prefix + separator + PLAN_EXCLUDE_BLOCK)


def validate_commit_parts(
    commit_type: str, subject: str, scope: str | None = None
) -> None:
    if not isinstance(commit_type, str) or not CONVENTIONAL_TYPE_RE.fullmatch(
        commit_type
    ):
        die(
            "commit_type must start with a lowercase letter and contain only "
            "lowercase letters, digits, or hyphens"
        )
    if scope is not None and (
        not isinstance(scope, str) or not CONVENTIONAL_SCOPE_RE.fullmatch(scope)
    ):
        die(
            "commit_scope must start with a lowercase letter or digit and contain "
            "only lowercase letters, digits, dots, underscores, slashes, or hyphens"
        )
    if not isinstance(subject, str) or not subject.strip():
        die("commit subject must be non-empty")
    if subject != subject.strip() or "\n" in subject or "\r" in subject:
        die("commit subject must be a trimmed single line")


def make_conventional_commit_message(
    commit_type: str, subject: str, scope: str | None = None
) -> str:
    validate_commit_parts(commit_type, subject, scope)
    prefix = f"{commit_type}({scope})" if scope else commit_type
    return f"{prefix}: {subject}"


def validate_conventional_commit_message(message: str) -> None:
    if not CONVENTIONAL_COMMIT_RE.fullmatch(message):
        raise GitError(
            "commit message must match Conventional Commit syntax: "
            "type(scope): subject"
        )


def git_commit_repo(repo_root: Path, message: str, allow_empty: bool = False) -> None:
    """Commit all changes in a secondary workspace repository. Unlike
    git_commit_all, it has no .plan/ machinery (secondary repos never host .plan)."""
    validate_conventional_commit_message(message)
    r = git_run(["add", "-A"], repo_root)
    if r.returncode != 0:
        raise GitError(f"git add failed: {r.stderr.strip()}")
    r = git_run(["diff", "--cached", "--quiet"], repo_root)
    if r.returncode == 0 and not allow_empty:
        raise GitError("nothing to commit (no staged project changes)")
    commit_args = ["commit", "-m", message]
    if allow_empty:
        commit_args.insert(1, "--allow-empty")
    r = git_run(commit_args, repo_root)
    if r.returncode != 0:
        raise GitError(f"git commit failed: {r.stderr.strip() or r.stdout.strip()}")


def git_commit_all(repo_root: Path, message: str, allow_empty: bool = False) -> None:
    """Commit project changes while guaranteeing .plan/ is not included."""
    validate_conventional_commit_message(message)
    ensure_plan_locally_excluded(repo_root)
    r = git_run(["diff", "--cached", "--name-only", "--", ".plan"], repo_root)
    if r.returncode != 0:
        raise GitError(f"staged .plan check failed: {r.stderr.strip()}")
    if r.stdout.strip():
        raise GitError(
            ".plan/ contains staged paths; unstage them before Outfit commits"
        )
    if git_plan_is_tracked(repo_root):
        raise GitError(
            ".plan/ is tracked by git; migrate it before Outfit commits"
        )
    r = git_run(["add", "-A"], repo_root)
    if r.returncode != 0:
        raise GitError(f"git add failed: {r.stderr.strip()}")
    r = git_run(["diff", "--cached", "--name-only", "--", ".plan"], repo_root)
    if r.returncode != 0:
        raise GitError(f"staged .plan check failed: {r.stderr.strip()}")
    if r.stdout.strip():
        raise GitError(".plan/ was staged unexpectedly; commit aborted")
    r = git_run(["diff", "--cached", "--quiet"], repo_root)
    if r.returncode == 0 and not allow_empty:
        raise GitError("nothing to commit (no staged project changes)")
    commit_args = ["commit", "-m", message]
    if allow_empty:
        commit_args.insert(1, "--allow-empty")
    r = git_run(commit_args, repo_root)
    if r.returncode != 0:
        raise GitError(f"git commit failed: {r.stderr.strip() or r.stdout.strip()}")
