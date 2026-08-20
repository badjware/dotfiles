#!/usr/bin/env python3
"""Dispatch tests for the primary working-tree execution model."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
DISPATCH = SCRIPTS / "dispatch.py"


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def setup_repo(tmp: Path) -> Path:
    root = tmp / "repo"
    root.mkdir()
    git(["init"], root)
    git(["config", "user.email", "test@test.com"], root)
    git(["config", "user.name", "Test"], root)
    git(["commit", "--allow-empty", "-m", "chore: test baseline"], root)

    exclude = root / ".git" / "info" / "exclude"
    exclude.write_text(exclude.read_text() + "\n.plan/\n")

    plan = root / ".plan"
    (plan / "stories").mkdir(parents=True)
    (plan / "work").mkdir()
    (plan / "decisions.md").write_text("# Decisions\n")
    (plan / "codebase.md").write_text("# Codebase map\n")
    (plan / "tasks.json").write_text(json.dumps({"tasks": [{
        "id": "T-001", "story_id": "S-001", "milestone": "M-001",
        "title": "test task", "description": "desc", "acceptance": ["it works"],
        "status": "in_progress", "depends_on": [],
    }]}))
    (plan / "status.json").write_text(json.dumps({"milestone_baselines": {}}))
    return root


def run_dispatch(root: Path, role: str, target: str) -> subprocess.CompletedProcess[str]:
    pi_dir = root / "bin"
    pi_dir.mkdir(exist_ok=True)
    pi = pi_dir / "pi"
    pi.write_text("#!/bin/sh\nexit 0\n")
    pi.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{pi_dir}:{env.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(DISPATCH), role, target, "--timeout", "5"],
        cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


class TestDispatchWorkingTree(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="outfit_dispatch_test_")
        self.root = setup_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_programmer_runs_from_the_primary_repository(self) -> None:
        result = run_dispatch(self.root, "programmer", "T-001")
        self.assertEqual(result.returncode, 0, result.stderr)

        session = next((self.root / ".plan" / "work").glob("*/session-programmer-*"))
        metadata = json.loads((session / "metadata.json").read_text())
        self.assertEqual(metadata["cwd"], str(self.root))

    def test_reviewer_runs_from_the_primary_repository(self) -> None:
        result = run_dispatch(self.root, "reviewer", "T-001")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_qa_rejects_task_ids(self) -> None:
        result = run_dispatch(self.root, "qa", "T-001")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a milestone ID", result.stderr)

    def test_milestone_qa_requires_a_recorded_baseline(self) -> None:
        result = run_dispatch(self.root, "qa", "M-001")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no recorded milestone_baselines[M-001]", result.stderr)

    def test_dispatch_does_not_modify_project_gitignore(self) -> None:
        result = run_dispatch(self.root, "programmer", "T-001")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".gitignore").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
