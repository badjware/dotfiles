#!/usr/bin/env python3
"""Task CRUD with state-machine enforcement. Sole writer of .plan/tasks.json."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    ID_LINK_RE,
    ID_MILESTONE_RE,
    ID_STORY_RE,
    ID_TASK_RE,
    TASK_STATUSES,
    TASK_TRANSITIONS,
    TERMINAL_STATUSES,
    GitError,
    check_acyclic,
    die,
    find_plan_dir,
    git_commit_all,
    git_commit_repo,
    git_run,
    latest_review_cycle,
    link_by_id,
    read_issues,
    read_links,
    read_workspace,
    repo_dirty,
    resolve_task_repo,
    make_conventional_commit_message,
    next_task_id,
    plan_lock,
    primary_repo_name,
    read_tasks,
    task_by_id,
    workspace_repo_path,
    validate_task_shape,
    work_dir_for_task,
    write_tasks,
)

# When transitioning into an active state, the status file for that role is stale
# from any prior round and must be cleared so dispatch produces a fresh result.
ROLE_FOR_STATUS = {
    "in_progress": "programmer",
    "in_review": "reviewer",
}


def _validate_repository(plan: Path, name: str) -> None:
    ws = read_workspace(plan)
    if ws is None:
        die("--repository requires a workspace manifest; run workspace.py add first")
    if name not in ws["repositories"]:
        die(f"--repository references unknown workspace repository {name!r}")


def _validate_link_ids(plan: Path, link_ids: list[str]) -> None:
    links = read_links(plan)["links"]
    for lid in link_ids:
        if not ID_LINK_RE.match(lid):
            die(f"--finalizes must match L-\\d{{3,}}: {lid!r}")
        if not link_by_id(links, lid):
            die(f"--finalizes references unknown link {lid}")


def _milestone_num(ms_id: str) -> int | None:
    """Return numeric part of milestone ID (M-001 -> 1), or None if unparseable."""
    try:
        return int(ms_id.split("-")[1])
    except (IndexError, ValueError):
        return None


def check_no_future_milestone_deps(
    tasks: list[dict], task_milestone: str, deps: list[str]
) -> None:
    """Reject dependencies on tasks in future milestones."""
    cur_num = _milestone_num(task_milestone)
    if cur_num is None:
        return
    for d in deps:
        dep_task = task_by_id(tasks, d)
        if dep_task is None:
            continue
        dep_num = _milestone_num(dep_task["milestone"])
        if dep_num is not None and dep_num > cur_num:
            die(
                f"depends_on {d} is in future milestone {dep_task['milestone']} "
                f"(task is in {task_milestone}); cross-milestone dependencies to "
                f"future milestones are not allowed"
            )


def cmd_add(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    if args.id and args.next:
        die("pass either --id or --next, not both")
    # Hold the lock across the read-modify-write so a concurrent add cannot
    # observe the same max ID and allocate a duplicate.
    with plan_lock(plan):
        return _add_locked(plan, args)


def _add_locked(plan: Path, args: argparse.Namespace) -> int:
    data = read_tasks(plan)
    tasks = data["tasks"]

    tid = next_task_id(tasks) if (args.next or not args.id) else args.id
    if not ID_TASK_RE.match(tid):
        die(f"--id must match T-\\d{{3,}}: {tid!r}")
    if task_by_id(tasks, tid):
        die(f"task {tid} already exists")
    if not ID_STORY_RE.match(args.story):
        die(f"--story must match S-\\d{{3,}}: {args.story!r}")
    # confirm story file exists
    matches = list((plan / "stories").glob(f"{args.story}-*.md"))
    if not matches:
        die(f"no story file found for {args.story} in {plan / 'stories'}")
    if not ID_MILESTONE_RE.match(args.milestone):
        die(f"--milestone must match M-\\d{{3,}}: {args.milestone!r}")

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
        "commit_type": args.commit_type,
    }
    if args.commit_scope:
        new["commit_scope"] = args.commit_scope
    if args.finalizes:
        _validate_link_ids(plan, args.finalizes)
        new["finalizes"] = list(args.finalizes)
    if args.repository:
        _validate_repository(plan, args.repository)
        new["repository"] = args.repository
    validate_task_shape(new)
    # check deps exist, acyclic, and not in future milestones
    for d in deps:
        if not task_by_id(tasks, d):
            die(f"depends_on references unknown task {d}")
    check_acyclic(tasks, new)
    check_no_future_milestone_deps(tasks, args.milestone, deps)

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
        print(
            f"{t['id']:<{w_id}}  {t['status']:<{w_st}}  {t['milestone']:<{w_ms}}  {t['title']}"
        )
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
        die(
            f"invalid transition {cur} -> {new_status} for {args.id}; allowed: {sorted(allowed) or 'none (terminal)'}",
            category="state",
        )
    # check deps for forward moves
    if new_status == "in_progress" and cur == "todo":
        for d in t["depends_on"]:
            dep = task_by_id(data["tasks"], d)
            if dep and dep["status"] != "done":
                die(
                    f"cannot start {args.id}: dependency {d} is {dep['status']}, not done",
                    category="state",
                )
    if new_status == "blocked" and not args.reason:
        die("--reason required when setting status to blocked")
    if new_status == "cancelled" and not args.reason:
        die("--reason required when setting status to cancelled")

    # T-014: a finalization task cannot complete against an unreleased dependency.
    if new_status == "done" and t.get("finalizes"):
        links = read_links(plan)["links"]
        for lid in t["finalizes"]:
            link = link_by_id(links, lid)
            if link and link["release_status"] != "released":
                die(
                    f"cannot complete finalization task {args.id}: linked dependency "
                    f"{lid} ({link['repository']}) is not released",
                    category="state",
                )

    commit_message = None
    if new_status == "done":
        if not t.get("commit_type"):
            die(
                f"cannot complete {args.id}: commit_type is missing; "
                "set it with task.py update"
            )
        commit_message = make_conventional_commit_message(
            t["commit_type"], t["title"], t.get("commit_scope")
        )

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
        wd = work_dir_for_task(plan, args.id)
        sf = wd / f"status-{ROLE_FOR_STATUS[new_status]}.md"
        if sf.exists():
            sf.unlink()

    # On transition to done, auto-commit in the task's declared repository.
    # Failure is fatal: revert the state change.
    if new_status == "done":
        repo_name, repo_path, is_primary = resolve_task_repo(plan, t)
        try:
            _guard_changes_confined_to_repo(plan, repo_name)
            if is_primary:
                git_commit_all(repo_path, commit_message)
            else:
                git_commit_repo(repo_path, commit_message)
        except GitError as e:
            t["status"] = cur
            write_tasks(plan, data)
            die(f"commit failed (state reverted to {cur}): {e}", category="commit")

    print(f"{args.id}: {cur} -> {new_status}")
    return 0


def _guard_changes_confined_to_repo(plan: Path, task_repo: str | None) -> None:
    """Refuse to complete a task if another declared repository has uncommitted
    changes (T-016): a task commits only in its own repository and must not leave
    changes elsewhere."""
    ws = read_workspace(plan)
    if ws is None:
        return
    primary = primary_repo_name(ws)
    target = task_repo or primary
    for name in ws["repositories"]:
        if name == target:
            continue
        path = workspace_repo_path(plan, ws, name)
        if repo_dirty(path, exclude_plan=(name == primary)):
            raise GitError(
                f"repository {name!r} has uncommitted changes but the task targets "
                f"{target!r}; a task must not leave changes in another repository"
            )


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
            die(f"--milestone must match M-\\d{{3,}}: {args.milestone!r}")
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
    if args.commit_type is not None:
        t["commit_type"] = args.commit_type
        changed.append("commit_type")
    if args.commit_scope is not None:
        if args.commit_scope:
            t["commit_scope"] = args.commit_scope
        else:
            t.pop("commit_scope", None)
        changed.append("commit_scope")
    if args.finalizes is not None:
        if args.finalizes:
            _validate_link_ids(plan, args.finalizes)
            t["finalizes"] = list(args.finalizes)
        else:
            t.pop("finalizes", None)
        changed.append("finalizes")
    if args.repository is not None:
        if args.repository:
            _validate_repository(plan, args.repository)
            t["repository"] = args.repository
        else:
            t.pop("repository", None)
        changed.append("repository")

    if not changed:
        die(
            "no fields to update; pass at least one editable task field"
        )

    validate_task_shape(t)
    check_acyclic(tasks)
    if "depends" in changed:
        check_no_future_milestone_deps(tasks, t["milestone"], t["depends_on"])
    write_tasks(plan, data)
    print(f"{args.id}: updated ({', '.join(changed)})")
    return 0


def cmd_user_edited(args: argparse.Namespace) -> int:
    """Record a direct user edit made during review (T-006).

    Captures a patch and file manifest, fingerprints the working tree, marks any
    prior reviewer approval stale, and flags that verification is required. A
    fresh reviewer must be dispatched afterward; workers must preserve the
    recorded changes.
    """
    plan = find_plan_dir()
    with plan_lock(plan):
        data = read_tasks(plan)
        t = task_by_id(data["tasks"], args.id)
        if not t:
            die(f"no task {args.id}")
        if t["status"] != "in_review":
            die(
                f"user-edited requires {args.id} to be in_review (current: {t['status']})",
                category="state",
            )
        root = plan.parent
        scope = ["--", ".", ":(exclude).plan", ":(exclude).plan/**"]
        status = git_run(["status", "--porcelain", *scope], root)
        if status.returncode != 0:
            die(f"git status failed: {status.stderr.strip()}", category="state")
        files = [line[3:] for line in status.stdout.splitlines() if line.strip()]
        # Intent-to-add so untracked files appear in the diff, then reset so the
        # index returns to HEAD (Outfit stages only at commit time).
        git_run(["add", "-N", *scope], root)
        diff = git_run(["diff", "HEAD", *scope], root)
        git_run(["reset", "-q", *scope], root)
        if diff.returncode != 0:
            die(f"git diff failed: {diff.stderr.strip()}", category="state")
        fingerprint = hashlib.sha256(diff.stdout.encode()).hexdigest()

        wd = work_dir_for_task(plan, args.id)
        wd.mkdir(parents=True, exist_ok=True)
        n = len(list(wd.glob("user-edit-*.patch"))) + 1
        (wd / f"user-edit-{n:02d}.patch").write_text(diff.stdout)
        (wd / f"user-edit-manifest-{n:02d}.md").write_text(
            "# User-edit manifest\n\n"
            + "\n".join(f"- {f}" for f in files)
            + ("\n" if files else "(no project file changes detected)\n")
        )
        edits = t.setdefault("user_edits", [])
        edits.append(
            {
                "n": n,
                "fingerprint": fingerprint,
                "files": files,
                "verified": False,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
        )
        write_tasks(plan, data)

        # Mark prior reviewer approval stale so a fresh reviewer must run.
        sf = wd / "status-reviewer.md"
        if sf.exists():
            sf.unlink()

    print(f"{args.id}: recorded user edit #{n} ({len(files)} file(s))")
    print(f"  patch:    {wd / f'user-edit-{n:02d}.patch'}")
    print("  reviewer approval marked stale; dispatch a fresh reviewer")
    print("  run the project build/test verification before completing this task")
    return 0


def cmd_amend(args: argparse.Namespace) -> int:
    """Apply a task-local acceptance amendment (T-008).

    Only current-task fields may change here (title, description, acceptance).
    Changes requiring rediscovery (new story, milestone, actors, scope) are not
    accepted; return to discovery for those. History is append-only.
    """
    plan = find_plan_dir()
    with plan_lock(plan):
        data = read_tasks(plan)
        tasks = data["tasks"]
        t = task_by_id(tasks, args.id)
        if not t:
            die(f"no task {args.id}")
        if t["status"] in TERMINAL_STATUSES:
            die(f"cannot amend {args.id}: status is {t['status']} (terminal)", category="state")
        changes: dict = {}
        if args.title is not None:
            changes["title"] = args.title
            t["title"] = args.title
        if args.description is not None:
            changes["description"] = args.description
            t["description"] = args.description
        if args.acceptance is not None:
            if not args.acceptance:
                die("--acceptance requires at least one value")
            changes["acceptance"] = list(args.acceptance)
            t["acceptance"] = list(args.acceptance)
        if not changes:
            die("amend requires at least one of --title, --description, --acceptance")
        validate_task_shape(t)
        history = t.setdefault("amendments", [])
        history.append(
            {
                "reason": args.reason,
                "changes": changes,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
        )
        write_tasks(plan, data)
    print(f"{args.id}: amended ({', '.join(changes)})")
    print("  workers now receive the latest approved acceptance")
    return 0


def cmd_review_state(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    if not task_by_id(data["tasks"], args.id):
        die(f"no task {args.id}")
    wd = work_dir_for_task(plan, args.id)
    cycle = latest_review_cycle(wd)
    print(f"task:          {args.id}")
    print(f"latest_cycle:  {cycle if cycle else '(none)'}")
    if cycle:
        for kind in ("review", "human-review", "review-response"):
            f = wd / f"{kind}-{cycle:02d}.md"
            print(f"  {kind}-{cycle:02d}.md: {'present' if f.exists() else 'missing'}")
    open_issues = [
        i
        for i in read_issues(plan)["issues"]
        if i["source_task"] == args.id and i["status"] == "open"
    ]
    print(f"open_issues:   {len(open_issues)}")
    for i in open_issues:
        print(f"  {i['id']}  {i['severity']}  {i['description']}")
    return 0


def cmd_work_dir(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    data = read_tasks(plan)
    t = task_by_id(data["tasks"], args.id)
    if not t:
        die(f"no task {args.id}")
    wd = work_dir_for_task(plan, args.id)
    print(str(wd))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add a new task")
    p_add.add_argument("--id", help="explicit task id (default: auto T-NNN)")
    p_add.add_argument(
        "--next",
        action="store_true",
        help="allocate the next available task id atomically (mutually exclusive with --id)",
    )
    p_add.add_argument("--story", required=True, help="story id, e.g. S-001")
    p_add.add_argument("--milestone", required=True, help="milestone id, e.g. M-001")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", default="")
    p_add.add_argument(
        "--commit-type",
        required=True,
        help="Conventional Commit type, subject to project-specific rules",
    )
    p_add.add_argument(
        "--commit-scope", help="optional Conventional Commit scope"
    )
    p_add.add_argument(
        "--acceptance",
        action="append",
        required=True,
        help="acceptance criterion (repeatable, at least one)",
    )
    p_add.add_argument(
        "--depends", action="append", help="dependency task id (repeatable)"
    )
    p_add.add_argument(
        "--finalizes",
        action="append",
        help="link id (L-NNN) this task finalizes (repeatable)",
    )
    p_add.add_argument(
        "--repository",
        help="workspace repository this task targets (default: primary)",
    )
    p_add.set_defaults(func=cmd_add)

    p_get = sub.add_parser("get", help="print one task as JSON")
    p_get.add_argument("id")
    p_get.set_defaults(func=cmd_get)

    p_list = sub.add_parser("list", help="list tasks")
    p_list.add_argument("--status", help="filter by status")
    p_list.add_argument("--status-not", help="exclude this status")
    p_list.add_argument("--milestone", help="filter by milestone")
    p_list.add_argument(
        "--include-cancelled",
        action="store_true",
        help="include cancelled tasks (excluded by default)",
    )
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
    p_upd.add_argument(
        "--commit-type", help="replace the Conventional Commit type"
    )
    p_upd.add_argument(
        "--commit-scope",
        help="replace the Conventional Commit scope; pass an empty string to clear",
    )
    p_upd.add_argument(
        "--acceptance",
        action="append",
        help="replace acceptance list (repeatable; pass each criterion as a separate --acceptance)",
    )
    p_upd.add_argument(
        "--depends",
        action="append",
        help="replace depends_on list (repeatable; omit to leave unchanged)",
    )
    p_upd.add_argument(
        "--finalizes",
        action="append",
        help="replace finalizes list (repeatable; pass empty to clear)",
    )
    p_upd.add_argument(
        "--repository",
        help="change target workspace repository (pass empty to clear)",
    )
    p_upd.set_defaults(func=cmd_update)

    p_wd = sub.add_parser(
        "work-dir",
        help="print the work directory path for a task (handles slug-based names)",
    )
    p_wd.add_argument("id")
    p_wd.set_defaults(func=cmd_work_dir)

    p_rs = sub.add_parser(
        "review-state",
        help="show the latest review cycle and open issues for a task",
    )
    p_rs.add_argument("id")
    p_rs.set_defaults(func=cmd_review_state)

    p_ue = sub.add_parser(
        "user-edited",
        help="record a direct user edit during review (marks review stale)",
    )
    p_ue.add_argument("id")
    p_ue.set_defaults(func=cmd_user_edited)

    p_am = sub.add_parser(
        "amend", help="apply a task-local acceptance amendment (append-only)"
    )
    p_am.add_argument("id")
    p_am.add_argument("--reason", required=True, help="why the amendment is needed")
    p_am.add_argument("--title")
    p_am.add_argument("--description")
    p_am.add_argument(
        "--acceptance",
        action="append",
        help="replace acceptance list (repeatable)",
    )
    p_am.set_defaults(func=cmd_amend)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
