#!/usr/bin/env python3
"""Dispatch a worker (programmer | reviewer | qa) for one task.

Silent to caller by design: streams the worker's full transcript to
.plan/work/<task-id>/worker.log and returns to stdout only:
  - exit code line
  - contents of .plan/work/<task-id>/status.md (if present)
  - on non-zero exit, last ~20 lines of worker.log
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import die, find_plan_dir, read_tasks, skill_dir, task_by_id  # noqa: E402

VALID_ROLES = {"programmer", "reviewer", "qa"}
DEFAULT_TIMEOUT = 900  # seconds (15 min)
TAIL_LINES = 20


def tail(path: Path, n: int) -> str:
    if not path.exists():
        return "(no log)"
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                read = min(block, size)
                size -= read
                f.seek(size)
                data = f.read(read) + data
        lines = data.decode("utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError as e:
        return f"(could not read log: {e})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("role", choices=sorted(VALID_ROLES))
    ap.add_argument("task_id")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"worker timeout in seconds (default: {DEFAULT_TIMEOUT})")
    ap.add_argument("--context", default="",
                    help="extra context to append to the worker prompt (e.g. review notes on rework)")
    args = ap.parse_args()

    if shutil.which("pi") is None:
        die("`pi` not found on PATH")

    plan = find_plan_dir()
    tasks = read_tasks(plan)["tasks"]
    if not task_by_id(tasks, args.task_id):
        die(f"unknown task {args.task_id}")

    sd = skill_dir()
    role_file = sd / "roles" / f"{args.role}.md"
    if not role_file.is_file():
        die(f"role file missing: {role_file}")
    role_content = role_file.read_text()
    task_script = sd / "scripts" / "task.py"

    work_dir = plan / "work" / args.task_id
    work_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    session_dir = work_dir / f"session-{args.role}-{ts}"
    session_dir.mkdir()
    log_path = work_dir / "worker.log"
    status_path = work_dir / "status.md"
    # clear stale status from a prior run on rework
    if status_path.exists():
        status_path.unlink()

    prompt = (
        f"Task: {args.task_id}.\n"
        f"You are a {args.role} worker. Your role specification is in your system prompt.\n"
        f"State directory: .plan/ (in your cwd).\n"
        f"\n"
        f"Get your task spec by running:\n"
        f"  {task_script} get {args.task_id}\n"
        f"Also read for context:\n"
        f"  .plan/stories/  (the story referenced by your task's story_id)\n"
        f"  .plan/decisions.md  (project constraints)\n"
        f"\n"
        f"Your scratch directory (the only place you write inside .plan/): "
        f".plan/work/{args.task_id}/\n"
        f"Write status.md last with one of: done | blocked | needs-changes.\n"
    )
    if args.context:
        prompt += f"\nAdditional context:\n{args.context}\n"

    cmd = [
        "pi", "-p",
        "--append-system-prompt", role_content,
        "--session-dir", str(session_dir),
        prompt,
    ]

    # cwd is the project root (parent of .plan/)
    project_root = plan.parent

    timed_out = False
    rc: int
    with log_path.open("w") as logf:
        logf.write(f"# dispatch {args.role} {args.task_id} @ {ts}\n")
        logf.write(f"# cwd={project_root}\n")
        logf.write(f"# session={session_dir}\n\n")
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

    if timed_out:
        # synthesize a blocked status so the lead has something to read
        status_path.write_text(f"blocked\nworker exceeded timeout of {args.timeout}s\n")

    # Output to caller (the lead): minimal, structured.
    print(f"exit_code: {rc}")
    print(f"worker_log: {log_path}")
    if status_path.exists():
        print("--- status.md ---")
        print(status_path.read_text().rstrip())
        print("--- end status.md ---")
    else:
        print("(no status.md written by worker)")
    if rc != 0:
        print(f"--- last {TAIL_LINES} lines of worker.log ---")
        print(tail(log_path, TAIL_LINES))
        print("--- end log tail ---")
    return rc if rc in (0, 124) else 1


if __name__ == "__main__":
    sys.exit(main())
