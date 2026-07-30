#!/usr/bin/env python3
"""Tests for M-002: error categories, amendments, user edits, rework tracking."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
PLAN_INIT = SCRIPTS / "plan-init.py"
TASK = SCRIPTS / "task.py"
ISSUE = SCRIPTS / "issue.py"
sys.path.insert(0, str(SCRIPTS))
from _state import ERROR_EXIT_CODES, REWORK_ATTEMPT_LIMIT, parse_worker_status  # noqa: E402


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def new_project(root: Path) -> Path:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    run([sys.executable, str(PLAN_INIT), "--dir", str(root)], root)
    plan = root / ".plan"
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    return plan


def add_task(root: Path) -> str:
    r = run(
        [sys.executable, str(TASK), "add", "--next", "--story", "S-001",
         "--milestone", "M-001", "--title", "a task", "--commit-type", "feat",
         "--acceptance", "works"],
        root,
    )
    return json.loads(r.stdout)["id"]


class TestErrorCategories(unittest.TestCase):
    def test_state_error_on_invalid_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            r = run([sys.executable, str(TASK), "set-status", "T-001", "done"],
                    root, check=False)
            self.assertEqual(r.returncode, ERROR_EXIT_CODES["state"])
            self.assertIn("error[state]", r.stderr)

    def test_usage_error_distinct_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            r = run([sys.executable, str(TASK), "get", "T-999"], root, check=False)
            self.assertEqual(r.returncode, ERROR_EXIT_CODES["usage"])
            self.assertIn("error[usage]", r.stderr)


class TestAmendments(unittest.TestCase):
    def test_amend_is_append_only_and_updates_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            run([sys.executable, str(TASK), "amend", "T-001", "--reason", "clarify",
                 "--acceptance", "works precisely"], root)
            run([sys.executable, str(TASK), "amend", "T-001", "--reason", "reword",
                 "--title", "the task"], root)
            t = json.loads(run([sys.executable, str(TASK), "get", "T-001"], root).stdout)
            self.assertEqual(t["acceptance"], ["works precisely"])
            self.assertEqual(t["title"], "the task")
            self.assertEqual(len(t["amendments"]), 2)

    def test_amend_requires_a_change_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            r = run([sys.executable, str(TASK), "amend", "T-001", "--reason", "x"],
                    root, check=False)
            self.assertNotEqual(r.returncode, 0)


class TestUserEdits(unittest.TestCase):
    def test_user_edit_captures_patch_and_marks_review_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            add_task(root)
            run([sys.executable, str(TASK), "set-status", "T-001", "in_progress"], root)
            (root / "app.py").write_text("print('hi')\n")
            run([sys.executable, str(TASK), "set-status", "T-001", "in_review"], root)
            wd = Path(run([sys.executable, str(TASK), "work-dir", "T-001"], root).stdout.strip())
            wd.mkdir(parents=True, exist_ok=True)
            (wd / "status-reviewer.md").write_text("done\n")
            (root / "app.py").write_text("print('hi')\nprint('user')\n")

            run([sys.executable, str(TASK), "user-edited", "T-001"], root)

            self.assertTrue((wd / "user-edit-01.patch").exists())
            self.assertIn("print('user')", (wd / "user-edit-01.patch").read_text())
            self.assertFalse((wd / "status-reviewer.md").exists())
            t = json.loads(run([sys.executable, str(TASK), "get", "T-001"], root).stdout)
            self.assertEqual(len(t["user_edits"]), 1)
            self.assertFalse(t["user_edits"][0]["verified"])
            # Index must be left clean (== HEAD).
            self.assertEqual(
                subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=root,
                               text=True, capture_output=True).stdout, "")

    def test_user_edit_rejected_outside_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            r = run([sys.executable, str(TASK), "user-edited", "T-001"], root, check=False)
            self.assertNotEqual(r.returncode, 0)


class TestReworkTracking(unittest.TestCase):
    def test_attempts_escalate_at_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            run([sys.executable, str(ISSUE), "add", "--source-task", "T-001",
                 "--severity", "major", "--category", "correctness",
                 "--description", "bug"], root)
            out = ""
            for _ in range(REWORK_ATTEMPT_LIMIT):
                out = run([sys.executable, str(ISSUE), "attempt", "I-001"], root).stdout
            self.assertIn("ESCALATE", out)

    def test_repeated_rejection_escalates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            run([sys.executable, str(ISSUE), "add", "--source-task", "T-001",
                 "--severity", "major", "--category", "correctness",
                 "--description", "bug"], root)
            run([sys.executable, str(ISSUE), "reject", "I-001", "--cycle", "1",
                 "--rationale", "no"], root)
            out = run([sys.executable, str(ISSUE), "reject", "I-001", "--cycle", "2",
                       "--rationale", "still no"], root).stdout
            self.assertIn("ESCALATE", out)


class TestWorkerStatusParsing(unittest.TestCase):
    def test_parse_status_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "status.md"
            p.write_text("blocked\nneeds an API key\n")
            self.assertEqual(parse_worker_status(p), ("blocked", "needs an API key"))
            p.write_text("done\n")
            self.assertEqual(parse_worker_status(p), ("done", ""))
            self.assertEqual(parse_worker_status(Path(tmp) / "missing.md"), (None, ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
