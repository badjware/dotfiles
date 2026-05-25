#!/usr/bin/env python3
"""Initialize .plan/ in the current directory and ensure a git repo is set up.

Behavior:
  - Creates .plan/ scaffold (refuses to clobber an existing .plan/).
  - If cwd is not a git repo, runs `git init`.
  - If cwd is a git repo with commits and a dirty working tree, refuses with a
    helpful message (the user must clean up before running outfit; this script
    will not modify pre-existing changes).
  - Ensures .gitignore excludes worker logs and pi session directories.
  - Makes an initial commit of the .plan/ scaffold (and .gitignore).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    GitError, atomic_write_json, die, git_commit_all, git_head_sha, git_is_repo,
    git_run, git_working_tree_dirty, skill_dir,
)

GITIGNORE_BLOCK = "\n# outfit: keep curated artifacts, ignore verbose logs/sessions\n.plan/work/*/worker.log\n.plan/work/*/session-*/\n"


def ensure_gitignore(root: Path) -> None:
    gi = root / ".gitignore"
    existing = gi.read_text() if gi.exists() else ""
    if "outfit: keep curated artifacts" in existing:
        return
    new = existing
    if existing and not existing.endswith("\n"):
        new += "\n"
    new += GITIGNORE_BLOCK
    gi.write_text(new)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".", help="project directory (default: cwd)")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    plan = root / ".plan"
    if plan.exists():
        die(f"{plan} already exists; refusing to clobber")

    # Ensure git repo. If pre-existing with commits, refuse on dirty working tree.
    if not git_is_repo(root):
        r = git_run(["init"], root)
        if r.returncode != 0:
            die(f"git init failed: {r.stderr.strip()}")
        print(f"initialized git repo at {root}")
    else:
        head = git_head_sha(root)
        if head is not None:
            try:
                if git_working_tree_dirty(root):
                    die("working tree is dirty; clean it up before running outfit (commit, stash, reset, restore, etc. - the user's choice)")
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

    atomic_write_json(plan / "tasks.json", {"tasks": []})
    atomic_write_json(plan / "status.json", {
        "phase": "discovery",
        "current_milestone": None,
        "gate_1_approved": False,
        "milestone_gates": {},
    })

    ensure_gitignore(root)

    # Initial commit of the scaffold.
    try:
        git_commit_all(root, "outfit: initialize .plan/")
    except GitError as e:
        die(f"initial commit failed: {e}")

    print(f"initialized {plan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
