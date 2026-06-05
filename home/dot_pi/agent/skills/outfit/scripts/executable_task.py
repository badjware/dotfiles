#!/usr/bin/env python3
"""Task CRUD with state-machine enforcement. Sole writer of .plan/tasks.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    GitError, ID_MILESTONE_RE, ID_STORY_RE, ID_TASK_RE, TASK_STATUSES,
    TASK_TRANSITIONS, TERMINAL_STATUSES, check_acyclic, die, find_plan_dir,
    git_commit_all, next_task_id, read_tasks, task_by_id, validate_task_shape,
    write_tasks,
)

# When transitioning into an active state, the status file for that role is stale
# from any prior round and must be cleared so dispatch produces a fresh result.
ROLE_FOR_STATUS = {
    "in_progress": "programmer",
    "in_review": "reviewer",
}


def cmd_add(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    tasks = data["tasks"]

    tid = args.id or next_task_id(tasks)
    if not ID_TASK_RE.match(tid):
        die(f"--id must match T-\\d{{3,}}: {tid!r}")
    if task_by_id(tasks, tid):
        die(f"task {tid} already exists")
    if not ID_STORY_RE.match(args.story):
        die(f"--story must match S-\\d{{3,}}: {args.story!r}")
    # confirm story file exists
    matches = list((plan / "stories").glob(f"{args.story}-*.md"))
    if not matches:
        die(f"no story file found for {args.story} in {plan/'stories'}")
    if not ID_MILESTONE_RE.match(args.milestone):
        die(f"--milestone must match M\\d+: {args.milestone!r}")

    deps = args.depends or []
    new = {
        "id": tid,
        "story_id": args.story,
        "milestone": args.milestone,
        "title": args.title,
        "description": args.description,
        "acceptance": args.acceptance,
        "status": "todo",
        "depends_on": deps,
    }
    validate_task_shape(new)
    # check deps exist and acyclic
    for d in deps:
        if not task_by_id(tasks, d):
            die(f"depends_on references unknown task {d}")
    check_acyclic(tasks, new)

    tasks.append(new)
    write_tasks(plan, data)
    print(json.dumps(new, indent=2))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    t = task_by_id(data["tasks"], args.id)
    if not t:
        die(f"no task {args.id}")
    print(json.dumps(t, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    tasks = data["tasks"]
    if not args.include_cancelled:
        tasks = [t for t in tasks if t["status"] != "cancelled"]
    if args.status:
        tasks = [t for t in tasks if t["status"] == args.status]
    if args.status_not:
        tasks = [t for t in tasks if t["status"] != args.status_not]
    if args.milestone:
        tasks = [t for t in tasks if t["milestone"] == args.milestone]
    if not tasks:
        print("(no tasks)")
        return 0
    # compact table
    w_id = max(len(t["id"]) for t in tasks)
    w_st = max(len(t["status"]) for t in tasks)
    w_ms = max(len(t["milestone"]) for t in tasks)
    for t in tasks:
        print(f"{t['id']:<{w_id}}  {t['status']:<{w_st}}  {t['milestone']:<{w_ms}}  {t['title']}")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    t = task_by_id(data["tasks"], args.id)
    if not t:
        die(f"no task {args.id}")
    new_status = args.status
    if new_status not in TASK_STATUSES:
        die(f"unknown status {new_status!r}; valid: {sorted(TASK_STATUSES)}")
    cur = t["status"]
    if new_status == cur:
        die(f"task {args.id} is already {cur}")
    allowed = TASK_TRANSITIONS.get(cur, set())
    if new_status not in allowed:
        die(f"invalid transition {cur} -> {new_status} for {args.id}; allowed: {sorted(allowed) or 'none (terminal)'}")
    # check deps for forward moves
    if new_status == "in_progress" and cur == "todo":
        for d in t["depends_on"]:
            dep = task_by_id(data["tasks"], d)
            if dep and dep["status"] != "done":
                die(f"cannot start {args.id}: dependency {d} is {dep['status']}, not done")
    if new_status == "blocked" and not args.reason:
        die("--reason required when setting status to blocked")
    if new_status == "cancelled" and not args.reason:
        die("--reason required when setting status to cancelled")

    t["status"] = new_status
    if new_status == "blocked":
        t["blocked_reason"] = args.reason
    elif "blocked_reason" in t and new_status != "blocked":
        del t["blocked_reason"]
    if new_status == "cancelled":
        t["cancelled_reason"] = args.reason
    write_tasks(plan, data)

    # Clear the now-stale status file for the role matching the new active state,
    # so dispatch produces a fresh result for this round.
    if new_status in ROLE_FOR_STATUS:
        sf = plan / "work" / args.id / f"status-{ROLE_FOR_STATUS[new_status]}.md"
        if sf.exists():
            sf.unlink()

    # On transition to done, auto-commit. Failure is fatal: revert the state change.
    if new_status == "done":
        try:
            git_commit_all(plan.parent, f"outfit: {args.id} {t['title']}")
        except GitError as e:
            t["status"] = cur
            write_tasks(plan, data)
            die(f"commit failed (state reverted to {cur}): {e}")

    print(f"{args.id}: {cur} -> {new_status}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    tasks = data["tasks"]
    t = task_by_id(tasks, args.id)
    if not t:
        die(f"no task {args.id}")
    if t["status"] in TERMINAL_STATUSES:
        die(f"cannot update {args.id}: status is {t['status']} (terminal)")

    changed = []
    if args.title is not None:
        t["title"] = args.title
        changed.append("title")
    if args.description is not None:
        t["description"] = args.description
        changed.append("description")
    if args.milestone is not None:
        if not ID_MILESTONE_RE.match(args.milestone):
            die(f"--milestone must match M\\d+: {args.milestone!r}")
        t["milestone"] = args.milestone
        changed.append("milestone")
    if args.acceptance is not None:
        if not args.acceptance:
            die("--acceptance requires at least one value")
        for a in args.acceptance:
            if not a:
                die("acceptance criterion must be non-empty")
        t["acceptance"] = list(args.acceptance)
        changed.append("acceptance")
    if args.depends is not None:
        for d in args.depends:
            if not ID_TASK_RE.match(d):
                die(f"--depends must match T-\\d{{3,}}: {d!r}")
            if not task_by_id(tasks, d):
                die(f"--depends references unknown task {d}")
            if d == t["id"]:
                die("task cannot depend on itself")
        t["depends_on"] = list(args.depends)
        changed.append("depends")

    if not changed:
        die("no fields to update; pass at least one of --title/--description/--milestone/--acceptance/--depends")

    validate_task_shape(t)
    check_acyclic(tasks)
    write_tasks(plan, data)
    print(f"{args.id}: updated ({', '.join(changed)})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add a new task")
    p_add.add_argument("--id", help="task id (default: auto T-NNN)")
    p_add.add_argument("--story", required=True, help="story id, e.g. S-001")
    p_add.add_argument("--milestone", required=True, help="milestone id, e.g. M1")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", default="")
    p_add.add_argument("--acceptance", action="append", required=True,
                       help="acceptance criterion (repeatable, at least one)")
    p_add.add_argument("--depends", action="append", help="dependency task id (repeatable)")
    p_add.set_defaults(func=cmd_add)

    p_get = sub.add_parser("get", help="print one task as JSON")
    p_get.add_argument("id")
    p_get.set_defaults(func=cmd_get)

    p_list = sub.add_parser("list", help="list tasks")
    p_list.add_argument("--status", help="filter by status")
    p_list.add_argument("--status-not", help="exclude this status")
    p_list.add_argument("--milestone", help="filter by milestone")
    p_list.add_argument("--include-cancelled", action="store_true",
                        help="include cancelled tasks (excluded by default)")
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set-status", help="transition a task to a new status")
    p_set.add_argument("id")
    p_set.add_argument("status")
    p_set.add_argument("--reason", help="required when transitioning to blocked")
    p_set.set_defaults(func=cmd_set_status)

    p_upd = sub.add_parser("update", help="update an in-flight task's editable fields")
    p_upd.add_argument("id")
    p_upd.add_argument("--title")
    p_upd.add_argument("--description")
    p_upd.add_argument("--milestone")
    p_upd.add_argument("--acceptance", action="append",
                       help="replace acceptance list (repeatable; pass each criterion as a separate --acceptance)")
    p_upd.add_argument("--depends", action="append",
                       help="replace depends_on list (repeatable; omit to leave unchanged)")
    p_upd.set_defaults(func=cmd_update)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
