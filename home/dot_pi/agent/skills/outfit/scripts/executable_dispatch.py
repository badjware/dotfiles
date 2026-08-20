#!/usr/bin/env python3
"""Dispatch a worker (programmer | reviewer | qa) for one task or milestone.

For programmer and reviewer: dispatch for a specific task ID.
For qa: dispatch for a specific milestone ID.

Silent to caller by design: streams the worker's output to
.plan/work/<id>/session-<role>-<timestamp>/output.log and returns to stdout only:
  - exit code line
  - contents of .plan/work/<id>/status-<role>.md (if present)
  - on non-zero exit, last ~20 lines of output.log

Dispatch metadata (role, task, model, baseline, timestamp, duration, exit_code)
is written to .plan/work/<id>/session-<role>-<timestamp>/metadata.json.

If --context is provided (rework notes), it is written to
.plan/work/<id>/rework-context.md for the audit trail before dispatch.

Per-role model selection is honored via env vars:
  OUTFIT_MODEL_PROGRAMMER, OUTFIT_MODEL_REVIEWER, OUTFIT_MODEL_QA
If unset, pi's default model is used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import json as _json

from _state import (  # noqa: E402
    ID_MILESTONE_RE,
    die,
    find_plan_dir,
    git_head_sha,
    git_is_ancestor,
    latest_review_cycle,
    parse_worker_status,
    make_work_dir_name,
    read_status,
    read_tasks,
    resolve_task_repo,
    skill_dir,
    task_by_id,
)

VALID_ROLES = {"programmer", "reviewer", "qa"}
DEFAULT_TIMEOUT = 900  # seconds (15 min)
TAIL_LINES = 20


def tail(path: Path, n: int) -> str:
    if not path.exists():
        return "(no log)"
    r = subprocess.run(
        ["tail", "-n", str(n), str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if r.returncode != 0:
        return f"(could not read log: {r.stderr.strip()})"
    return r.stdout.rstrip("\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("role", choices=sorted(VALID_ROLES))
    ap.add_argument(
        "target_id", help="task ID (for programmer/reviewer) or milestone ID (for qa)"
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"worker timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    ap.add_argument(
        "--context",
        default="",
        help="extra context to append to the worker prompt (e.g. review notes on rework)",
    )
    args = ap.parse_args()

    if shutil.which("pi") is None:
        die("`pi` not found on PATH")

    plan = find_plan_dir()
    project_root = plan.parent
    tasks = read_tasks(plan)["tasks"]

    # For QA, target_id is a milestone ID or the literal "project"; for
    # programmer/reviewer, it's a task.
    is_milestone_dispatch = args.role == "qa"
    qa_scope = None
    if is_milestone_dispatch:
        if args.target_id == "project":
            qa_scope = "project"
            target_display = "project"
            work_id = "project"
        elif ID_MILESTONE_RE.match(args.target_id):
            qa_scope = "milestone"
            target_display = f"milestone {args.target_id}"
            work_id = args.target_id
        else:
            die(f"QA dispatch requires a milestone ID (M-NNN) or 'project': {args.target_id!r}")
    else:
        task = task_by_id(tasks, args.target_id)
        if not task:
            die(f"unknown task {args.target_id}")
        target_display = f"task {args.target_id}"
        work_id = make_work_dir_name(args.target_id, task["title"])

    sd = skill_dir()
    role_file = sd / "roles" / f"{args.role}.md"
    if not role_file.is_file():
        die(f"role file missing: {role_file}")
    role_content = role_file.read_text()
    task_script = sd / "scripts" / "task.py"

    work_dir = plan / "work" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)
    start = dt.datetime.now()
    ts = start.strftime("%Y%m%d-%H%M%S-%f")
    session_dir = work_dir / f"session-{args.role}-{ts}"
    session_dir.mkdir()
    log_path = session_dir / "output.log"
    status_path = work_dir / f"status-{args.role}.md"
    # clear stale status from a prior run of this role
    if status_path.exists():
        status_path.unlink()

    # Write rework context to audit file before dispatch
    if args.context:
        (work_dir / "rework-context.md").write_text(args.context)

    # Per-role model
    model = os.environ.get(f"OUTFIT_MODEL_{args.role.upper()}")

    # Baseline for diff-based review. For programmer/reviewer it is HEAD at
    # dispatch. For QA it is the recorded milestone/project start baseline
    # (T-011/T-012), never HEAD at QA time, so QA sees the full scope diff.
    if is_milestone_dispatch:
        status = read_status(plan)
        if qa_scope == "project":
            baseline = status.get("project_baseline") or status.get(
                "milestone_baselines", {}
            ).get("M-001")
            src = "project_baseline"
        else:
            baseline = status.get("milestone_baselines", {}).get(args.target_id)
            src = f"milestone_baselines[{args.target_id}]"
        if not baseline:
            die(
                f"no recorded {src}; run status.py set-milestone / approve-gate-1 first",
                category="state",
            )
        head = git_head_sha(project_root)
        if head and not git_is_ancestor(project_root, baseline, head):
            die(
                f"recorded QA baseline {baseline[:12]} is not an ancestor of HEAD; "
                "the milestone history was rewritten",
                category="state",
            )
        task_repo_name, task_repo_path = None, project_root
    else:
        # A task's baseline is HEAD of its declared repository (T-016).
        task_repo_name, task_repo_path, _ = resolve_task_repo(plan, task)
        baseline = git_head_sha(task_repo_path)
    baseline_file = work_dir / f"baseline-{args.role}.sha"
    baseline_file.write_text((baseline or "") + "\n")

    if is_milestone_dispatch and qa_scope == "project":
        prompt = (
            f"Project-level QA (all milestones).\n"
            f"You are a {args.role} worker. Your role specification is in your system prompt.\n"
            f"State directory: .plan/ (in your cwd).\n"
            f"\n"
            f"This is the whole-project release QA, distinct from per-milestone QA.\n"
            f"Verify every story across all milestones and cross-milestone integration:\n"
            f"  {task_script} list            (all tasks)\n"
            f"Read .plan/plan.md, all .plan/stories/, .plan/decisions.md, .plan/codebase.md.\n"
            f"Check the open issue registry: {sd / 'scripts' / 'issue.py'} list\n"
            f"Run the project's full test, build, and vet/lint commands and record results.\n"
            f"Assess release readiness: temporary dependency replacements, dirty linked\n"
            f"repositories, and unreleased prerequisites.\n"
            f"If .plan/workspace.json exists, verify every declared repository builds and\n"
            f"tests, and that cross-repository dependency versions are compatible.\n"
            f"\n"
            f"Your scratch directory (the only place you write inside .plan/): "
            f".plan/work/{work_id}/\n"
            f"Write status-{args.role}.md last with one of: done | needs-changes.\n"
        )
    elif is_milestone_dispatch:
        prompt = (
            f"Milestone: {args.target_id}.\n"
            f"You are a {args.role} worker. Your role specification is in your system prompt.\n"
            f"State directory: .plan/ (in your cwd).\n"
            f"\n"
            f"Get tasks in this milestone by running:\n"
            f"  {task_script} list --milestone {args.target_id}\n"
            f"Read milestone spec from .plan/plan.md.\n"
            f"Read stories referenced by the milestone's tasks from .plan/stories/.\n"
            f"Also read for context:\n"
            f"  .plan/decisions.md  (project constraints)\n"
            f"  .plan/codebase.md  (accumulated codebase map)\n"
            f"\n"
            f"Your scratch directory (the only place you write inside .plan/): "
            f".plan/work/{work_id}/\n"
            f"Write status-{args.role}.md last with one of: done | needs-changes.\n"
        )
    else:
        # Cycle-numbered artifacts keep every review round immutable: a later
        # reviewer writes review-NN.md rather than overwriting review.md.
        prior_cycle = latest_review_cycle(work_dir)
        if args.role == "reviewer":
            cycle = prior_cycle + 1
            artifact_note = (
                f"Write your review to review-{cycle:02d}.md (do not overwrite "
                f"earlier review-NN.md files). Assign every finding a stable issue "
                f"ID via {sd / 'scripts' / 'issue.py'}.\n"
            )
        else:  # programmer
            cycle = prior_cycle
            if cycle >= 1:
                artifact_note = (
                    f"This is a rework of review cycle {cycle:02d}. Record your "
                    f"per-issue accepted/rejected decisions in "
                    f"review-response-{cycle:02d}.md, referencing stable issue IDs.\n"
                )
            else:
                artifact_note = ""
        rework_ctx_note = (
            f"\nIf .plan/work/{work_id}/rework-context.md exists, read it before starting work."
            f" It contains rework guidance from a previous review cycle.\n"
        )
        repo_note = ""
        if task_repo_name is not None:
            repo_note = (
                f"\nThis task targets workspace repository '{task_repo_name}' at "
                f"{task_repo_path}. Make and inspect changes there; do not modify "
                f"other repositories. The lead commits only in that repository.\n"
            )
        prompt = (
            f"Task: {args.target_id}.\n"
            f"You are a {args.role} worker. Your role specification is in your system prompt.\n"
            f"State directory: .plan/ (in your cwd).\n"
            f"{repo_note}"
            f"\n"
            f"Get your task spec by running:\n"
            f"  {task_script} get {args.target_id}\n"
            f"Also read for context:\n"
            f"  .plan/decisions.md  (project constraints)\n"
            f"  .plan/codebase.md  (accumulated codebase map; read before surveying source)\n"
            f"{rework_ctx_note}"
            f"\n"
            f"Your scratch directory (the only place you write inside .plan/): "
            f".plan/work/{work_id}/\n"
            f"{artifact_note}"
            f"Write status-{args.role}.md last with one of: done | blocked | needs-changes.\n"
        )
    if baseline:
        prompt += (
            f"\nThe git baseline at dispatch was {baseline}. "
            f"Use `git diff {baseline}` to see code changes made for this task.\n"
        )

    cmd = ["pi", "-p", "--no-extensions"]
    if model:
        cmd.extend(["--model", model])
    cmd.extend(
        [
            "--append-system-prompt",
            role_content,
            "--session-dir",
            str(session_dir),
            prompt,
        ]
    )

    timed_out = False
    rc: int
    with log_path.open("w") as logf:
        try:
            proc = subprocess.run(
                cmd,
                cwd=project_root,
                stdout=logf,
                stderr=subprocess.STDOUT,
                timeout=args.timeout,
                check=False,
            )
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = 124
    end = dt.datetime.now()
    duration = (end - start).total_seconds()

    # Write dispatch metadata to session directory for audit trail
    meta: dict = {
        "role": args.role,
        "target": target_display,
        "model": model or "(pi default)",
        "baseline_sha": baseline or "(no commits yet)",
        "cwd": str(project_root),
        "started": ts,
        "ended": end.strftime("%Y%m%d-%H%M%S"),
        "duration_s": round(duration, 1),
        "exit_code": rc,
    }
    if not is_milestone_dispatch:
        meta["task_title"] = task["title"]
        meta["review_cycle"] = cycle
    (session_dir / "metadata.json").write_text(_json.dumps(meta, indent=2) + "\n")

    if timed_out:
        status_path.write_text(f"blocked\nworker exceeded timeout of {args.timeout}s\n")

    # Output to caller (the lead): minimal, structured.
    print(f"exit_code: {rc}")
    print(f"session_dir: {session_dir}")
    if status_path.exists():
        print(f"--- status-{args.role}.md ---")
        print(status_path.read_text().rstrip())
        print(f"--- end status-{args.role}.md ---")
        # T-005: needs-changes and blocked must carry a concrete, structured reason.
        st, reason = parse_worker_status(status_path)
        if st in {"needs-changes", "blocked"} and not reason:
            print(
                f"WARNING: status '{st}' has no reason; a bare {st} is invalid "
                f"and must not be acted on (T-005)"
            )
    else:
        print(f"(no status-{args.role}.md written by worker)")
    if rc != 0:
        print(f"--- last {TAIL_LINES} lines of output.log ---")
        print(tail(log_path, TAIL_LINES))
        print("--- end log tail ---")
    return rc


if __name__ == "__main__":
    sys.exit(main())
