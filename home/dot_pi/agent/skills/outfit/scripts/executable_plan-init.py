#!/usr/bin/env python3
"""Initialize local .plan/ state and ensure a git repository is set up.

Outfit records .plan/ in .git/info/exclude and explicitly excludes it from every
staging operation. Project .gitignore files are never created or modified.
Repositories without HEAD receive a Conventional Commit baseline that excludes
.plan/; existing repositories receive no initialization commit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    GitError,
    atomic_write_json,
    die,
    git_commit_all,
    ensure_plan_locally_excluded,
    git_head_sha,
    git_is_repo,
    git_run,
    git_working_tree_dirty,
    skill_dir,
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dir", default=".", help="project directory (default: cwd)")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    plan = root / ".plan"
    if plan.exists():
        die(f"{plan} already exists; refusing to clobber")

    # Ensure git repo. If pre-existing with commits, refuse on dirty project files.
    if not git_is_repo(root):
        r = git_run(["init"], root)
        if r.returncode != 0:
            die(f"git init failed: {r.stderr.strip()}")
        print(f"initialized git repo at {root}")
    head = git_head_sha(root)
    if head is not None:
        try:
            if git_working_tree_dirty(root):
                die(
                    "working tree is dirty; clean it up before running outfit (commit, stash, reset, restore, etc. - the user's choice)"
                )
        except GitError as e:
            die(str(e))

    try:
        ensure_plan_locally_excluded(root)
    except GitError as e:
        die(str(e))

    # .plan/ scaffold
    (plan / "stories").mkdir(parents=True)
    (plan / "work").mkdir()

    template_plan = (skill_dir() / "templates" / "plan.md").read_text()
    (plan / "plan.md").write_text(template_plan)

    (plan / "decisions.md").write_text(
        "# Decisions\n\n<!-- Append-only log of project decisions. Newest at the bottom. -->\n"
    )

    (plan / "codebase.md").write_text(
        "# Codebase map\n\n"
        "<!-- Maintained by the programmer worker. Key modules, patterns, non-obvious conventions.\n"
        "     Keep it short. Prune stale entries before adding new ones. -->\n"
    )

    atomic_write_json(plan / "tasks.json", {"tasks": []})
    atomic_write_json(plan / "issues.json", {"issues": []})
    atomic_write_json(plan / "linked.json", {"links": []})
    atomic_write_json(
        plan / "status.json",
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "phase": "discovery",
            "current_milestone": None,
            "gate_1_approved": False,
            "milestone_gates": {},
        },
    )

    # Repositories without HEAD need a stable review baseline. Existing project
    # files are included, but local planning state is explicitly excluded.
    if head is None:
        try:
            git_commit_all(
                root, "chore: establish project baseline", allow_empty=True
            )
        except GitError as e:
            die(f"baseline commit failed: {e}")

    print(f"initialized {plan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
