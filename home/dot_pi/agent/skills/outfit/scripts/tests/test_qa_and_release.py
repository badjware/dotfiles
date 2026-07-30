#!/usr/bin/env python3
"""Tests for M-003: milestone baselines, project QA, and the release audit."""

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
AUDIT = SCRIPTS / "audit.py"
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


def new_project(root: Path) -> Path:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    run([sys.executable, str(PLAN_INIT), "--dir", str(root)], root)
    plan = root / ".plan"
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    return plan


def add_task(root: Path, milestone: str) -> str:
    r = run(
        [sys.executable, str(TASK), "add", "--next", "--story", "S-001",
         "--milestone", milestone, "--title", "a task", "--commit-type", "feat",
         "--acceptance", "works"],
        root,
    )
    return json.loads(r.stdout)["id"]


def complete_task(root: Path, tid: str, filename: str) -> None:
    run([sys.executable, str(TASK), "set-status", tid, "in_progress"], root)
    (root / filename).write_text("x\n")
    run([sys.executable, str(TASK), "set-status", tid, "in_review"], root)
    run([sys.executable, str(TASK), "set-status", tid, "done"], root)


def status_json(plan: Path) -> dict:
    return json.loads((plan / "status.json").read_text())


class TestMilestoneBaselines(unittest.TestCase):
    def test_baseline_recorded_at_start_and_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            add_task(root, "M-001")
            run([sys.executable, str(STATUS), "approve-discovery"], root)
            run([sys.executable, str(STATUS), "set-milestone", "M-001"], root)
            run([sys.executable, str(STATUS), "approve-gate-1"], root)
            base = status_json(plan)["milestone_baselines"]["M-001"]
            self.assertEqual(base, git(root, "rev-parse", "HEAD"))
            # Commit within the milestone; re-activating must not move the baseline.
            complete_task(root, "T-001", "a.py")
            run([sys.executable, str(STATUS), "set-milestone", "M-001"], root)
            self.assertEqual(status_json(plan)["milestone_baselines"]["M-001"], base)
            # A later milestone's baseline is after M-001's commits (middle case).
            add_task(root, "M-002")
            run([sys.executable, str(STATUS), "set-milestone", "M-002"], root)
            base2 = status_json(plan)["milestone_baselines"]["M-002"]
            self.assertNotEqual(base2, base)
            self.assertEqual(base2, git(root, "rev-parse", "HEAD"))

    def test_project_baseline_set_at_gate_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            add_task(root, "M-001")
            run([sys.executable, str(STATUS), "approve-discovery"], root)
            run([sys.executable, str(STATUS), "set-milestone", "M-001"], root)
            gate_head = git(root, "rev-parse", "HEAD")
            run([sys.executable, str(STATUS), "approve-gate-1"], root)
            self.assertEqual(status_json(plan)["project_baseline"], gate_head)


class TestReleaseAudit(unittest.TestCase):
    def test_clean_dirty_and_local_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            blockers, _, _ = run_audit(root)
            self.assertEqual(blockers, [])
            (root / "go.mod").write_text(
                "module x\n\ngo 1.21\n\nreplace a/b => ../b\n"
            )
            git(root, "add", "go.mod")
            git(root, "commit", "-m", "chore: mod")
            blockers, _, _ = run_audit(root)
            self.assertTrue(any("local module replacement" in b for b in blockers))
            blockers, warnings, _ = run_audit(root, allow_local_replacements=True)
            self.assertEqual(blockers, [])
            self.assertTrue(warnings)

    def test_dirty_tree_is_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            (root / "loose.py").write_text("x\n")
            blockers, _, _ = run_audit(root)
            self.assertTrue(any("uncommitted" in b for b in blockers))


class TestApproveProject(unittest.TestCase):
    def _project_to_qa(self, root: Path) -> Path:
        plan = new_project(root)
        add_task(root, "M-001")
        run([sys.executable, str(STATUS), "approve-discovery"], root)
        run([sys.executable, str(STATUS), "set-milestone", "M-001"], root)
        run([sys.executable, str(STATUS), "approve-gate-1"], root)
        complete_task(root, "T-001", "a.py")
        run([sys.executable, str(STATUS), "approve-milestone", "M-001"], root)
        return plan

    def test_refused_without_project_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project_to_qa(root)
            r = run([sys.executable, str(STATUS), "approve-project"], root, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("project QA has not run", r.stderr)

    def test_refused_when_milestone_unapproved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            add_task(root, "M-001")
            run([sys.executable, str(STATUS), "approve-discovery"], root)
            run([sys.executable, str(STATUS), "set-milestone", "M-001"], root)
            run([sys.executable, str(STATUS), "approve-gate-1"], root)
            (plan / "work" / "project").mkdir(parents=True)
            (plan / "work" / "project" / "status-qa.md").write_text("done\n")
            r = run([sys.executable, str(STATUS), "approve-project"], root, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not approved", r.stderr)

    def test_succeeds_when_qa_done_and_audit_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._project_to_qa(root)
            (plan / "work" / "project").mkdir(parents=True)
            (plan / "work" / "project" / "status-qa.md").write_text("done\n")
            run([sys.executable, str(STATUS), "approve-project"], root)
            self.assertTrue(status_json(plan)["release_ready"])

    def test_refused_when_project_qa_needs_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._project_to_qa(root)
            (plan / "work" / "project").mkdir(parents=True)
            (plan / "work" / "project" / "status-qa.md").write_text("needs-changes\nblocker found\n")
            r = run([sys.executable, str(STATUS), "approve-project"], root, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not done", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
