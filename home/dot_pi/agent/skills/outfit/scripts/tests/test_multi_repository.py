#!/usr/bin/env python3
"""Tests for M-004 Release 4: multi-repository workspace support (T-016)."""

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
STATUS = SCRIPTS / "status.py"
WORKSPACE = SCRIPTS / "workspace.py"
sys.path.insert(0, str(SCRIPTS))
from _state import resolve_task_repo  # noqa: E402
from audit import run_audit  # noqa: E402


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


def make_repo(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / "f.txt").write_text("baseline\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "chore: baseline")


def workspace_project(base: Path):
    """consumer (primary) + libcore (secondary) with both declared. Returns
    (consumer_path, plan)."""
    (base / "libcore").mkdir()
    make_repo(base / "libcore")
    consumer = base / "consumer"
    consumer.mkdir()
    make_repo(consumer)
    run([sys.executable, str(PLAN_INIT), "--dir", str(consumer)], consumer)
    plan = consumer / ".plan"
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    run([sys.executable, str(WORKSPACE), "add", "--name", "consumer", "--path", "."], consumer)
    run([sys.executable, str(WORKSPACE), "add", "--name", "libcore", "--path", "../libcore"], consumer)
    return consumer, plan


def add_task(root: Path, *extra: str) -> str:
    r = run(
        [sys.executable, str(TASK), "add", "--next", "--story", "S-001",
         "--milestone", "M-001", "--title", "a task", "--commit-type", "feat",
         "--acceptance", "works", *extra],
        root,
    )
    return json.loads(r.stdout)["id"]


class TestWorkspaceManifest(unittest.TestCase):
    def test_first_repo_must_be_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "libcore").mkdir()
            make_repo(base / "libcore")
            consumer = base / "consumer"
            consumer.mkdir()
            make_repo(consumer)
            run([sys.executable, str(PLAN_INIT), "--dir", str(consumer)], consumer)
            r = run([sys.executable, str(WORKSPACE), "add", "--name", "libcore",
                     "--path", "../libcore"], consumer, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("primary", r.stderr)

    def test_resolve_task_repo_defaults_to_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, plan = workspace_project(Path(tmp))
            add_task(consumer)
            add_task(consumer, "--repository", "libcore")
            tasks = json.loads((plan / "tasks.json").read_text())["tasks"]
            _, _, is_primary_1 = resolve_task_repo(plan, tasks[0])
            name2, path2, is_primary_2 = resolve_task_repo(plan, tasks[1])
            self.assertTrue(is_primary_1)
            self.assertEqual(name2, "libcore")
            self.assertFalse(is_primary_2)


class TestPerRepositoryCommits(unittest.TestCase):
    def _to_execution(self, consumer: Path) -> None:
        run([sys.executable, str(STATUS), "approve-discovery"], consumer)
        run([sys.executable, str(STATUS), "set-milestone", "M-001"], consumer)
        run([sys.executable, str(STATUS), "approve-gate-1"], consumer)

    def test_task_commits_only_in_its_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            consumer, _ = workspace_project(base)
            add_task(consumer, "--repository", "libcore")
            self._to_execution(consumer)
            run([sys.executable, str(TASK), "set-status", "T-001", "in_progress"], consumer)
            (base / "libcore" / "f.txt").write_text("changed\n")
            run([sys.executable, str(TASK), "set-status", "T-001", "in_review"], consumer)
            run([sys.executable, str(TASK), "set-status", "T-001", "done"], consumer)
            self.assertEqual(git(base / "libcore", "log", "-1", "--pretty=%s"), "feat: a task")
            self.assertEqual(git(consumer, "log", "-1", "--pretty=%s"), "chore: baseline")

    def test_leakage_into_other_repo_blocks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            consumer, plan = workspace_project(base)
            add_task(consumer)  # primary
            self._to_execution(consumer)
            run([sys.executable, str(TASK), "set-status", "T-001", "in_progress"], consumer)
            (consumer / "f.txt").write_text("legit\n")
            (base / "libcore" / "f.txt").write_text("stray\n")
            run([sys.executable, str(TASK), "set-status", "T-001", "in_review"], consumer)
            r = run([sys.executable, str(TASK), "set-status", "T-001", "done"], consumer, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("another repository", r.stderr)
            task = json.loads((plan / "tasks.json").read_text())["tasks"][0]
            self.assertEqual(task["status"], "in_review")


class TestWorkspaceAudit(unittest.TestCase):
    def test_audit_flags_dirty_secondary_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            consumer, _ = workspace_project(base)
            (base / "libcore" / "f.txt").write_text("dirty\n")
            blockers, _, _ = run_audit(consumer)
            self.assertTrue(any("libcore" in b for b in blockers))


if __name__ == "__main__":
    unittest.main(verbosity=2)
