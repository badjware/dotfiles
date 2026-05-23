"""Shared helpers for outfit scripts. Stdlib only."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# State machine for task status. The lead requests transitions; we validate.
TASK_STATUSES = {"todo", "in_progress", "in_review", "in_qa", "done", "blocked"}
# blocked is reachable from any non-terminal state (including todo).
TASK_TRANSITIONS: dict[str, set[str]] = {
    "todo": {"in_progress", "blocked"},
    "in_progress": {"in_review", "blocked"},
    "in_review": {"in_qa", "in_progress", "blocked"},
    "in_qa": {"done", "in_progress", "blocked"},
    "blocked": {"todo", "in_progress"},
    "done": set(),  # terminal
}

PHASES = {"discovery", "planning", "execution", "re-discovery"}

ID_TASK_RE = re.compile(r"^T-\d{3,}$")
ID_STORY_RE = re.compile(r"^S-\d{3,}$")
ID_MILESTONE_RE = re.compile(r"^M\d+$")


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def find_plan_dir(start: Path | None = None) -> Path:
    """Walk up from cwd to find .plan/. Error if not found."""
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        cand = d / ".plan"
        if cand.is_dir():
            return cand
    die("no .plan/ directory found from cwd; run scripts/plan-init.py first")


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
    if not isinstance(data, dict) or "tasks" not in data or not isinstance(data["tasks"], list):
        die("tasks.json malformed: expected {\"tasks\": [...]}")
    return data


def write_tasks(plan: Path, data: dict) -> None:
    atomic_write_json(plan / "tasks.json", data)


def read_status(plan: Path) -> dict:
    data = read_json(plan / "status.json")
    if not isinstance(data, dict):
        die("status.json malformed")
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
    required = {"id", "story_id", "milestone", "title", "description",
                "acceptance", "status", "depends_on"}
    missing = required - t.keys()
    if missing:
        die(f"task missing fields: {sorted(missing)}")
    if not ID_TASK_RE.match(t["id"]):
        die(f"task id must match T-\\d{{3,}}: {t['id']!r}")
    if not ID_STORY_RE.match(t["story_id"]):
        die(f"story_id must match S-\\d{{3,}}: {t['story_id']!r}")
    if not ID_MILESTONE_RE.match(t["milestone"]):
        die(f"milestone must match M\\d+: {t['milestone']!r}")
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


def check_acyclic(tasks: list[dict], new_task: dict | None = None) -> None:
    """DFS cycle check. If new_task given, validate as-if it were already in the list."""
    by_id = {t["id"]: t for t in tasks}
    if new_task is not None:
        by_id[new_task["id"]] = new_task
    color: dict[str, int] = {}  # 0=white, 1=gray, 2=black

    def visit(node: str, path: list[str]) -> None:
        c = color.get(node, 0)
        if c == 1:
            cycle = path[path.index(node):] + [node]
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


def next_task_id(tasks: list[dict]) -> str:
    nums = [int(t["id"].split("-")[1]) for t in tasks if ID_TASK_RE.match(t["id"])]
    n = (max(nums) + 1) if nums else 1
    return f"T-{n:03d}"


def skill_dir() -> Path:
    """Return the outfit skill directory (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent
