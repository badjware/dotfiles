#!/usr/bin/env python3
"""Authoritative issue registry. Sole writer of .plan/issues.json.

Replaces stale deferred-issues.md scanning: review findings and deferred work
get stable IDs and an explicit lifecycle (open -> resolved | accepted |
superseded). Resolved and accepted findings are retained for auditing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    ID_ISSUE_RE,
    ID_TASK_RE,
    ISSUE_SEVERITIES,
    ISSUE_STATUSES,
    REWORK_ATTEMPT_LIMIT,
    die,
    find_plan_dir,
    issue_by_id,
    next_issue_id,
    read_issues,
    read_tasks,
    task_by_id,
    write_issues,
)


def _require_task(plan: Path, task_id: str) -> None:
    if not ID_TASK_RE.match(task_id):
        die(f"task id must match T-\\d{{3,}}: {task_id!r}")
    tasks = read_tasks(plan)["tasks"]
    if not task_by_id(tasks, task_id):
        die(f"unknown task {task_id}")


def _get_open(plan: Path, issue_id: str) -> tuple[dict, dict, list]:
    if not ID_ISSUE_RE.match(issue_id):
        die(f"issue id must match I-\\d{{3,}}: {issue_id!r}")
    data = read_issues(plan)
    issue = issue_by_id(data["issues"], issue_id)
    if not issue:
        die(f"no issue {issue_id}")
    if issue["status"] != "open":
        die(f"issue {issue_id} is {issue['status']}, not open")
    return data, issue, data["issues"]


def cmd_add(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    _require_task(plan, args.source_task)
    if args.severity not in ISSUE_SEVERITIES:
        die(f"severity must be one of {sorted(ISSUE_SEVERITIES)}: {args.severity!r}")
    data = read_issues(plan)
    issues = data["issues"]
    iid = next_issue_id(issues)
    issue = {
        "id": iid,
        "status": "open",
        "source_task": args.source_task,
        "severity": args.severity,
        "category": args.category,
        "location": args.location or "",
        "description": args.description,
    }
    issues.append(issue)
    write_issues(plan, data)
    print(json.dumps(issue, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    issues = read_issues(plan)["issues"]
    # Default view is open issues only; gates rely on this.
    if not args.all and not args.status:
        issues = [i for i in issues if i["status"] == "open"]
    if args.status:
        if args.status not in ISSUE_STATUSES:
            die(f"unknown status {args.status!r}; valid: {sorted(ISSUE_STATUSES)}")
        issues = [i for i in issues if i["status"] == args.status]
    if args.task:
        issues = [i for i in issues if i["source_task"] == args.task]
    if args.severity:
        issues = [i for i in issues if i["severity"] == args.severity]
    if not issues:
        print("(no issues)")
        return 0
    w_id = max(len(i["id"]) for i in issues)
    w_st = max(len(i["status"]) for i in issues)
    w_sev = max(len(i["severity"]) for i in issues)
    for i in issues:
        loc = f" [{i['location']}]" if i.get("location") else ""
        print(
            f"{i['id']:<{w_id}}  {i['status']:<{w_st}}  {i['severity']:<{w_sev}}  "
            f"{i['source_task']}  {i['description']}{loc}"
        )
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    if args.by:
        _require_task(plan, args.by)
    data, issue, _ = _get_open(plan, args.id)
    issue["status"] = "resolved"
    if args.by:
        issue["resolution_task"] = args.by
    if args.decision:
        issue["decision"] = args.decision
    write_issues(plan, data)
    print(f"{args.id}: open -> resolved")
    return 0


def cmd_accept(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data, issue, _ = _get_open(plan, args.id)
    issue["status"] = "accepted"
    issue["decision"] = args.decision
    write_issues(plan, data)
    print(f"{args.id}: open -> accepted")
    return 0


def cmd_supersede(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data, issue, issues = _get_open(plan, args.id)
    if args.by:
        if not ID_ISSUE_RE.match(args.by):
            die(f"--by must match I-\\d{{3,}}: {args.by!r}")
        if not issue_by_id(issues, args.by):
            die(f"--by references unknown issue {args.by}")
        issue["superseded_by"] = args.by
    issue["status"] = "superseded"
    if args.decision:
        issue["decision"] = args.decision
    write_issues(plan, data)
    print(f"{args.id}: open -> superseded")
    return 0


def cmd_attempt(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data, issue, _ = _get_open(plan, args.id)
    issue["attempts"] = issue.get("attempts", 0) + 1
    write_issues(plan, data)
    n = issue["attempts"]
    print(f"{args.id}: attempt {n} of {REWORK_ATTEMPT_LIMIT}")
    if n >= REWORK_ATTEMPT_LIMIT:
        print(f"ESCALATE: {args.id} reached {n} failed attempts; escalate to the user")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data, issue, _ = _get_open(plan, args.id)
    rejections = issue.setdefault("rejections", [])
    rejections.append({"cycle": args.cycle, "rationale": args.rationale})
    write_issues(plan, data)
    print(f"{args.id}: rejection recorded (cycle {args.cycle}, {len(rejections)} total)")
    # Repeated rejection of the same issue is a stalemate signal.
    if len(rejections) >= 2:
        print(f"ESCALATE: {args.id} rejected {len(rejections)} times; escalate to the user")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="record a new issue (status open)")
    p_add.add_argument("--source-task", required=True, help="task that surfaced it")
    p_add.add_argument(
        "--severity", required=True, help=f"one of {sorted(ISSUE_SEVERITIES)}"
    )
    p_add.add_argument(
        "--category", required=True, help="free-form category, e.g. correctness, tests"
    )
    p_add.add_argument("--description", required=True)
    p_add.add_argument("--location", help="file:line or module (optional)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list issues (open only by default)")
    p_list.add_argument("--all", action="store_true", help="include every status")
    p_list.add_argument("--status", help="filter by status")
    p_list.add_argument("--task", help="filter by source task")
    p_list.add_argument("--severity", help="filter by severity")
    p_list.set_defaults(func=cmd_list)

    p_res = sub.add_parser("resolve", help="mark an open issue resolved")
    p_res.add_argument("id")
    p_res.add_argument("--by", help="resolution task id")
    p_res.add_argument("--decision", help="how it was resolved")
    p_res.set_defaults(func=cmd_resolve)

    p_acc = sub.add_parser("accept", help="accept an open issue as won't-fix")
    p_acc.add_argument("id")
    p_acc.add_argument("--decision", required=True, help="why it is accepted")
    p_acc.set_defaults(func=cmd_accept)

    p_sup = sub.add_parser("supersede", help="mark an open issue superseded")
    p_sup.add_argument("id")
    p_sup.add_argument("--by", help="issue id that supersedes it")
    p_sup.add_argument("--decision", help="context for supersession")
    p_sup.set_defaults(func=cmd_supersede)

    p_att = sub.add_parser(
        "attempt",
        help="record a failed rework attempt on an issue (escalates at the limit)",
    )
    p_att.add_argument("id")
    p_att.set_defaults(func=cmd_attempt)

    p_rej = sub.add_parser(
        "reject", help="record a programmer rejection of an issue"
    )
    p_rej.add_argument("id")
    p_rej.add_argument("--cycle", type=int, required=True, help="review cycle number")
    p_rej.add_argument("--rationale", required=True)
    p_rej.set_defaults(func=cmd_reject)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
