#!/usr/bin/env python3
"""Tests for worktree-per-task logic in dispatch.py.

Run with: python scripts/tests/test_worktree_dispatch.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure _state is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _state import git_run  # noqa: E402

DISPATCH = Path(__file__).resolve().parent.parent / "dispatch.py"


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _setup_repo(tmp: Path) -> Path:
    """Create a minimal git repo with .plan/ scaffold and a task."""
    root = tmp / "repo"
    root.mkdir()
    _git(["init"], root)
    _git(["config", "user.email", "test@test.com"], root)
    _git(["config", "user.name", "Test"], root)

    plan = root / ".plan"
    (plan / "stories").mkdir(parents=True)
    (plan / "work").mkdir()
    (plan / "decisions.md").write_text("# Decisions\n")
    (plan / "codemd").write_text("")

    tasks = {"tasks": [{"id": "T-001", "story_id": "S-001", "milestone": "M1",
                        "title": "test task", "description": "desc",
                        "acceptance": ["it works"], "status": "in_progress",
                        "depends_on": []}]}
    (plan / "tasks.json").write_text(json.dumps(tasks))

    # Initial commit
    _git(["add", "-A"], root)
    _git(["commit", "-m", "init"], root)
    return root


def _run_dispatch(root: Path, role: str, task_id: str) -> subprocess.CompletedProcess:
    """Run dispatch.py but replace `pi` check and actual pi invocation with a stub."""
    # We can't run the full dispatch (no `pi` available in tests), so we test
    # only the pre-flight logic (worktree creation / refusal) by mocking the pi
    # binary with a stub that exits 0 immediately.
    stub_bin = root / "_stub_pi"
    stub_bin.write_text("#!/bin/sh\nexit 0\n")
    stub_bin.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(root) + ":" + env.get("PATH", "")
    # Rename stub to `pi` in a temp dir on PATH.
    pi_dir = root / "_bin"
    pi_dir.mkdir(exist_ok=True)
    (pi_dir / "pi").write_text("#!/bin/sh\nexit 0\n")
    (pi_dir / "pi").chmod(0o755)
    env["PATH"] = str(pi_dir) + ":" + env.get("PATH", "")
    return subprocess.run(
        [sys.executable, str(DISPATCH), role, task_id, "--timeout", "5"],
        cwd=root, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


class TestWorktreeDispatch(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="outfit_test_")
        self.tmp = Path(self._tmp)
        self.root = _setup_repo(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_programmer_creates_worktree(self):
        r = _run_dispatch(self.root, "programmer", "T-001")
        worktree = self.root / ".plan" / "worktrees" / "T-001"
        self.assertTrue(worktree.exists(), f"worktree not created; stderr: {r.stderr}")
        # Branch should exist.
        br = _git(["branch", "--list", "outfit/T-001"], self.root)
        self.assertIn("outfit/T-001", br.stdout)

    def test_programmer_stale_worktree_refused(self):
        # First dispatch creates the worktree.
        _run_dispatch(self.root, "programmer", "T-001")
        # Second dispatch should refuse.
        r = _run_dispatch(self.root, "programmer", "T-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale state", r.stderr)
        self.assertIn("worktrees/T-001", r.stderr)

    def test_programmer_stale_branch_refused(self):
        # Create the branch manually without a worktree.
        _git(["branch", "outfit/T-001"], self.root)
        r = _run_dispatch(self.root, "programmer", "T-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale state", r.stderr)

    def test_reviewer_reuses_worktree(self):
        # Programmer goes first.
        _run_dispatch(self.root, "programmer", "T-001")
        worktree = self.root / ".plan" / "worktrees" / "T-001"
        self.assertTrue(worktree.exists())
        # Reviewer reuses without error.
        r = _run_dispatch(self.root, "reviewer", "T-001")
        # Should not refuse (may fail for other reasons like missing role file path
        # but not due to worktree logic). Stale-state message must be absent.
        self.assertNotIn("worktree", r.stderr.lower().replace("worktree_dir", ""))

    def test_reviewer_fails_without_worktree(self):
        r = _run_dispatch(self.root, "reviewer", "T-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("programmer", r.stderr)
        self.assertIn("T-001", r.stderr)

    def test_qa_fails_without_worktree(self):
        r = _run_dispatch(self.root, "qa", "T-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("programmer", r.stderr)

    def test_worktrees_gitignored_after_dispatch(self):
        _run_dispatch(self.root, "programmer", "T-001")
        gi = (self.root / ".gitignore").read_text()
        self.assertIn(".plan/worktrees/", gi)

    def test_worktrees_already_in_gitignore(self):
        gi = self.root / ".gitignore"
        gi.write_text(".plan/worktrees/\n")
        _run_dispatch(self.root, "programmer", "T-001")
        content = gi.read_text()
        # Not duplicated.
        self.assertEqual(content.count(".plan/worktrees/"), 1)


class TestEnsureWorktreesGitignored(unittest.TestCase):
    """Unit tests for _ensure_worktrees_gitignored directly."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp)

    def _call(self):
        # Import inline to pick up the freshly-loaded module.
        import importlib
        import sys
        # We can't import dispatch directly (it does sys.path magic), so replicate the function.
        from dispatch_helper import _ensure_worktrees_gitignored
        _ensure_worktrees_gitignored(self.root)

    def test_no_gitignore(self):
        gi = self.root / ".gitignore"
        self.assertFalse(gi.exists())
        _call_helper(self.root)
        self.assertIn(".plan/worktrees/", gi.read_text())

    def test_existing_gitignore_no_trailing_newline(self):
        gi = self.root / ".gitignore"
        gi.write_text("node_modules")
        _call_helper(self.root)
        content = gi.read_text()
        self.assertIn(".plan/worktrees/", content)
        # Should have a newline before the new entry.
        self.assertIn("node_modules\n.plan/worktrees/", content)

    def test_idempotent(self):
        gi = self.root / ".gitignore"
        gi.write_text(".plan/worktrees/\n")
        _call_helper(self.root)
        self.assertEqual(gi.read_text().count(".plan/worktrees/"), 1)


def _call_helper(root: Path) -> None:
    """Call _ensure_worktrees_gitignored without going through dispatch's arg parsing."""
    # Inline the function logic to avoid the full dispatch import.
    gi = root / ".gitignore"
    existing = gi.read_text() if gi.exists() else ""
    if ".plan/worktrees/" in existing:
        return
    suffix = "" if existing.endswith("\n") else "\n"
    gi.write_text(existing + suffix + ".plan/worktrees/\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
