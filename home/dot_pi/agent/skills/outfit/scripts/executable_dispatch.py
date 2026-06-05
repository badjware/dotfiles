#!/usr/bin/env python3
"""Dispatch a worker (programmer | reviewer | qa) for one task or milestone.

For programmer and reviewer: dispatch for a specific task ID.
For qa: dispatch for a specific milestone ID.

Silent to caller by design: streams the worker's full transcript to
.plan/work/<id>/worker.log and returns to stdout only:
  - exit code line
  - contents of .plan/work/<id>/status-<role>.md (if present)
  - on non-zero exit, last ~20 lines of worker.log

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
from _state import (  # noqa: E402
    ID_MILESTONE_RE, die, find_plan_dir, git_head_sha, read_tasks, skill_dir,
    task_by_id,
)

VALID_ROLES = {"programmer", "reviewer", "qa"}
DEFAULT_TIMEOUT = 900  # seconds (15 min)
TAIL_LINES = 20


def tail(path: Path, n: int) -> str:
    if not path.exists():
        return "(no log)"
    r = subprocess.run(["tail", "-n", str(n), str(path)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        return f"(could not read log: {r.stderr.strip()})"
    return r.stdout.rstrip("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("role", choices=sorted(VALID_ROLES))
    ap.add_argument("target_id", help="task ID (for programmer/reviewer) or milestone ID (for qa)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"worker timeout in seconds (default: {DEFAULT_TIMEOUT})")
    ap.add_argument("--context", default="",
                    help="extra context to append to the worker prompt (e.g. review notes on rework)")
    args = ap.parse_args()

    if shutil.which("pi") is None:
        die("`pi` not found on PATH")

    plan = find_plan_dir()
    project_root = plan.parent
    tasks = read_tasks(plan)["tasks"]

    # For QA, target_id is a milestone; for programmer/reviewer, it's a task
    is_milestone_dispatch = (args.role == "qa")
    if is_milestone_dispatch:
        if not ID_MILESTONE_RE.match(args.target_id):
            die(f"QA dispatch requires milestone ID (M\\d+): {args.target_id!r}")
        target_display = f"milestone {args.target_id}"
        work_id = args.target_id
    else:
        task = task_by_id(tasks, args.target_id)
        if not task:
            die(f"unknown task {args.target_id}")
        target_display = f"task {args.target_id}"
        work_id = args.target_id

    sd = skill_dir()
    role_file = sd / "roles" / f"{args.role}.md"
    if not role_file.is_file():
        die(f"role file missing: {role_file}")
    role_content = role_file.read_text()
    task_script = sd / "scripts" / "task.py"

    work_dir = plan / "work" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)
    start = dt.datetime.now()
    ts = start.strftime("%Y%m%d-%H%M%S")
    session_dir = work_dir / f"session-{args.role}-{ts}"
    session_dir.mkdir()
    log_path = work_dir / "worker.log"
    status_path = work_dir / f"status-{args.role}.md"
    # clear stale status from a prior run of this role
    if status_path.exists():
        status_path.unlink()

    # Per-role model
    model = os.environ.get(f"OUTFIT_MODEL_{args.role.upper()}")

    # Baseline (HEAD at dispatch time) for diff-based review
    baseline = git_head_sha(project_root)
    baseline_file = work_dir / f"baseline-{args.role}.sha"
    baseline_file.write_text((baseline or "") + "\n")

    if is_milestone_dispatch:
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
        prompt = (
            f"Task: {args.target_id}.\n"
            f"You are a {args.role} worker. Your role specification is in your system prompt.\n"
            f"State directory: .plan/ (in your cwd).\n"
            f"\n"
            f"Get your task spec by running:\n"
            f"  {task_script} get {args.target_id}\n"
            f"Also read for context:\n"
            f"  .plan/stories/  (the story referenced by your task's story_id)\n"
            f"  .plan/decisions.md  (project constraints)\n"
            f"  .plan/codebase.md  (accumulated codebase map; read before surveying source)\n"
            f"\n"
            f"Your scratch directory (the only place you write inside .plan/): "
            f".plan/work/{work_id}/\n"
            f"Write status-{args.role}.md last with one of: done | blocked | needs-changes.\n"
        )
    if baseline:
        prompt += (
            f"\nThe git baseline at dispatch was {baseline}. "
            f"Use `git diff {baseline}` to see code changes made for this task.\n"
        )
    if args.context:
        prompt += f"\nAdditional context:\n{args.context}\n"

    cmd = ["pi", "-p"]
    if model:
        cmd.extend(["--model", model])
    cmd.extend([
        "--append-system-prompt", role_content,
        "--session-dir", str(session_dir),
        prompt,
    ])

    timed_out = False
    rc: int
    with log_path.open("w") as logf:
        logf.write("# outfit dispatch\n")
        logf.write(f"# role:         {args.role}\n")
        logf.write(f"# target:       {target_display}\n")
        if not is_milestone_dispatch:
            logf.write(f"# task_title:   {task['title']}\n")
        logf.write(f"# model:        {model or '(pi default)'}\n")
        logf.write(f"# baseline_sha: {baseline or '(no commits yet)'}\n")
        logf.write(f"# session:      {session_dir}\n")
        logf.write(f"# cwd:          {project_root}\n")
        logf.write(f"# started:      {ts}\n\n")
        logf.flush()
        try:
            proc = subprocess.run(
                cmd, cwd=project_root, stdout=logf, stderr=subprocess.STDOUT,
                timeout=args.timeout, check=False,
            )
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = 124
        end = dt.datetime.now()
        duration = (end - start).total_seconds()
        logf.write(f"\n# exit_code:    {rc}\n")
        logf.write(f"# duration_s:   {duration:.1f}\n")
        logf.write(f"# ended:        {end.strftime('%Y%m%d-%H%M%S')}\n")

    if timed_out:
        status_path.write_text(f"blocked\nworker exceeded timeout of {args.timeout}s\n")

    # Output to caller (the lead): minimal, structured.
    print(f"exit_code: {rc}")
    print(f"worker_log: {log_path}")
    if status_path.exists():
        print(f"--- status-{args.role}.md ---")
        print(status_path.read_text().rstrip())
        print(f"--- end status-{args.role}.md ---")
    else:
        print(f"(no status-{args.role}.md written by worker)")
    if rc != 0:
        print(f"--- last {TAIL_LINES} lines of worker.log ---")
        print(tail(log_path, TAIL_LINES))
        print("--- end log tail ---")
    return rc


if __name__ == "__main__":
    sys.exit(main())
