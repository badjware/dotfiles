#!/usr/bin/env python3
"""Tests for M-004 Release 3: linked-project handoffs (T-015) and dependency
finalization tasks (T-014)."""

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
LINKED = SCRIPTS / "linked.py"
sys.path.insert(0, str(SCRIPTS))
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


def make_repo(root: Path, initial: str = "baseline") -> None:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / "f.txt").write_text(f"{initial}\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "chore: baseline")


def consumer_with_link(base: Path):
    """Create linked repo + consumer with one pending override link. Returns
    (consumer_path, plan, required_commit, released_commit, link_id)."""
    linked = base / "libcore"
    linked.mkdir()
    make_repo(linked, "v1")
    required = git(linked, "rev-parse", "HEAD")
    (linked / "f.txt").write_text("v2\n")
    git(linked, "commit", "-am", "feat: v2")
    released = git(linked, "rev-parse", "HEAD")

    consumer = base / "consumer"
    consumer.mkdir()
    make_repo(consumer)
    run([sys.executable, str(PLAN_INIT), "--dir", str(consumer)], consumer)
    plan = consumer / ".plan"
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    r = run(
        [sys.executable, str(LINKED), "add", "--repository", "../libcore",
         "--required-commit", required, "--temporary-override", "../libcore"],
        consumer,
    )
    lid = json.loads(r.stdout)["id"]
    return consumer, plan, required, released, lid


def add_task(root: Path, *extra: str) -> str:
    r = run(
        [sys.executable, str(TASK), "add", "--next", "--story", "S-001",
         "--milestone", "M-001", "--title", "a task", "--commit-type", "feat",
         "--acceptance", "works", *extra],
        root,
    )
    return json.loads(r.stdout)["id"]


class TestLinkedHandoffs(unittest.TestCase):
    def test_set_released_accepts_version_containing_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, _, _, released, lid = consumer_with_link(Path(tmp))
            # The released commit descends from the required commit, so it is accepted.
            run([sys.executable, str(LINKED), "set-released", "--id", lid,
                 "--version", released], consumer)

    def test_set_released_rejects_version_missing_required_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, _, required, released, _ = consumer_with_link(Path(tmp))
            # Add a link whose required commit is the newer one, then try to
            # release the older version that lacks it.
            r = run([sys.executable, str(LINKED), "add", "--repository", "../libcore",
                     "--required-commit", released], consumer)
            lid = json.loads(r.stdout)["id"]
            r = run([sys.executable, str(LINKED), "set-released", "--id", lid,
                     "--version", required], consumer, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("does not contain required commit", r.stderr)

    def test_set_released_clears_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, plan, required, released, lid = consumer_with_link(Path(tmp))
            run([sys.executable, str(LINKED), "set-released", "--id", lid,
                 "--version", released], consumer)
            link = json.loads((plan / "linked.json").read_text())["links"][0]
            self.assertEqual(link["release_status"], "released")
            self.assertIsNone(link["temporary_override"])


class TestFinalizationTasks(unittest.TestCase):
    def _to_planning(self, consumer: Path) -> None:
        run([sys.executable, str(STATUS), "approve-discovery"], consumer)
        run([sys.executable, str(STATUS), "set-milestone", "M-001"], consumer)

    def test_gate1_requires_finalization_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, _, _, _, lid = consumer_with_link(Path(tmp))
            add_task(consumer)
            self._to_planning(consumer)
            r = run([sys.executable, str(STATUS), "approve-gate-1"], consumer, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("no finalization task", r.stderr)
            add_task(consumer, "--finalizes", lid)
            run([sys.executable, str(STATUS), "approve-gate-1"], consumer)

    def test_finalization_task_blocks_until_released(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, _, _, released, lid = consumer_with_link(Path(tmp))
            fin = add_task(consumer, "--finalizes", lid)
            self._to_planning(consumer)
            run([sys.executable, str(STATUS), "approve-gate-1"], consumer)
            run([sys.executable, str(TASK), "set-status", fin, "in_progress"], consumer)
            (consumer / "x.txt").write_text("x\n")
            run([sys.executable, str(TASK), "set-status", fin, "in_review"], consumer)
            r = run([sys.executable, str(TASK), "set-status", fin, "done"], consumer, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not released", r.stderr)
            run([sys.executable, str(LINKED), "set-released", "--id", lid,
                 "--version", released], consumer)
            run([sys.executable, str(TASK), "set-status", fin, "done"], consumer)

    def test_audit_flags_override_and_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer, plan, _, _, _ = consumer_with_link(Path(tmp))
            blockers, _, _ = run_audit(consumer)
            self.assertTrue(any("temporary override" in b for b in blockers))


if __name__ == "__main__":
    unittest.main(verbosity=2)
