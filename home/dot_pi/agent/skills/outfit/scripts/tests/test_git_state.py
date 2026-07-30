#!/usr/bin/env python3
"""Tests for local planning state and Conventional Commit behavior."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
PLAN_INIT = SCRIPTS / "plan-init.py"
STATUS = SCRIPTS / "status.py"
TASK = SCRIPTS / "task.py"
sys.path.insert(0, str(SCRIPTS))
from _state import (  # noqa: E402
    GitError,
    ensure_plan_locally_excluded,
    git_commit_all,
    git_working_tree_dirty,
    make_conventional_commit_message,
)


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", *args], root, check=check)


def init_repo(root: Path, with_head: bool = True) -> None:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    if with_head:
        (root / "README.md").write_text("baseline\n")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "chore: establish test baseline")


def write_plan(root: Path, task_status: str = "in_review") -> Path:
    plan = root / ".plan"
    (plan / "stories").mkdir(parents=True)
    (plan / "work").mkdir()
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    (plan / "plan.md").write_text("# Plan\n")
    (plan / "decisions.md").write_text("# Decisions\n")
    (plan / "codebase.md").write_text("# Codebase\n")
    (plan / "tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T-001",
                        "story_id": "S-001",
                        "milestone": "M-001",
                        "title": "handle expired sessions",
                        "description": "",
                        "acceptance": ["expired sessions are rejected"],
                        "status": task_status,
                        "depends_on": [],
                        "commit_type": "fix",
                        "commit_scope": "auth",
                    }
                ]
            }
        )
    )
    (plan / "status.json").write_text(
        json.dumps(
            {
                "phase": "discovery",
                "current_milestone": "M-001",
                "gate_1_approved": False,
                "milestone_gates": {},
            }
        )
    )
    ensure_plan_locally_excluded(root)
    return plan


class TestPlanInitialization(unittest.TestCase):
    def test_existing_repository_does_not_touch_gitignore_or_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            gitignore = root / ".gitignore"
            gitignore.write_text("node_modules\n")
            git(root, "add", ".gitignore")
            git(root, "commit", "-m", "chore: add ignores")
            before = git(root, "rev-parse", "HEAD").stdout.strip()

            run([sys.executable, str(PLAN_INIT), "--dir", str(root)], root)

            self.assertEqual(gitignore.read_text(), "node_modules\n")
            self.assertEqual(git(root, "rev-parse", "HEAD").stdout.strip(), before)
            self.assertEqual(git(root, "ls-files", "--", ".plan").stdout, "")
            exclude_path = Path(
                git(root, "rev-parse", "--git-path", "info/exclude").stdout.strip()
            )
            if not exclude_path.is_absolute():
                exclude_path = root / exclude_path
            self.assertIn(".plan/", exclude_path.read_text())

    def test_greenfield_gets_conventional_empty_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root, with_head=False)

            run([sys.executable, str(PLAN_INIT), "--dir", str(root)], root)

            self.assertEqual(
                git(root, "log", "-1", "--pretty=%s").stdout.strip(),
                "chore: establish project baseline",
            )
            self.assertEqual(git(root, "ls-files").stdout, "")
            self.assertFalse((root / ".gitignore").exists())


class TestGitSafety(unittest.TestCase):
    def test_dirty_check_ignores_plan_but_detects_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_plan(root)
            self.assertFalse(git_working_tree_dirty(root))
            (root / "source.py").write_text("print('changed')\n")
            self.assertTrue(git_working_tree_dirty(root))

    def test_commit_excludes_plan_and_uses_conventional_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            plan = write_plan(root)
            (root / "source.py").write_text("changed = True\n")
            (plan / "notes.md").write_text("local only\n")

            git_commit_all(root, "feat(core): add source behavior")

            self.assertEqual(git(root, "ls-files", "--", ".plan").stdout, "")
            self.assertEqual(
                git(root, "log", "-1", "--pretty=%s").stdout.strip(),
                "feat(core): add source behavior",
            )

    def test_pre_staged_plan_aborts_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            plan = write_plan(root)
            (plan / "forced.md").write_text("staged\n")
            git(root, "add", "-f", ".plan/forced.md")
            (root / "source.py").write_text("changed = True\n")

            with self.assertRaisesRegex(GitError, "staged paths"):
                git_commit_all(root, "feat: add behavior")

    def test_commit_message_builder(self) -> None:
        self.assertEqual(
            make_conventional_commit_message("fix", "handle expiry", "auth"),
            "fix(auth): handle expiry",
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            make_conventional_commit_message("Fix", "handle expiry")


class TestWorkflowCommits(unittest.TestCase):
    def test_gate_transitions_do_not_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            plan = write_plan(root, task_status="done")
            before = git(root, "rev-parse", "HEAD").stdout.strip()

            run([sys.executable, str(STATUS), "approve-discovery"], root)
            run([sys.executable, str(STATUS), "approve-gate-1"], root)
            run([sys.executable, str(STATUS), "approve-milestone", "M-001"], root)

            self.assertEqual(git(root, "rev-parse", "HEAD").stdout.strip(), before)
            status = json.loads((plan / "status.json").read_text())
            self.assertEqual(status["phase"], "execution")
            self.assertEqual(status["milestone_gates"]["M-001"], "approved")

    def test_task_done_uses_task_commit_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_plan(root)
            (root / "session.py").write_text("expired = True\n")

            run([sys.executable, str(TASK), "set-status", "T-001", "done"], root)

            self.assertEqual(
                git(root, "log", "-1", "--pretty=%s").stdout.strip(),
                "fix(auth): handle expired sessions",
            )
            self.assertEqual(git(root, "ls-files", "--", ".plan").stdout, "")

    def test_task_without_project_changes_reverts_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            plan = write_plan(root)

            result = run(
                [sys.executable, str(TASK), "set-status", "T-001", "done"],
                root,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            task = json.loads((plan / "tasks.json").read_text())["tasks"][0]
            self.assertEqual(task["status"], "in_review")

    def test_legacy_tracked_plan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_plan(root)
            git(root, "add", "-f", ".plan/tasks.json")
            git(root, "commit", "-m", "chore: legacy planning state")

            result = run(
                [sys.executable, str(TASK), "list"], root, check=False
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tracked by git", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
