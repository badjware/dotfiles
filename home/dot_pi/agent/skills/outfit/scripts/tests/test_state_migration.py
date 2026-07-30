#!/usr/bin/env python3
"""Tests for M-001: schema versioning/migration, issue registry, atomic task IDs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
PLAN_INIT = SCRIPTS / "plan-init.py"
MIGRATE = SCRIPTS / "migrate.py"
ISSUE = SCRIPTS / "issue.py"
TASK = SCRIPTS / "task.py"
STATUS = SCRIPTS / "status.py"
sys.path.insert(0, str(SCRIPTS))
from _state import CURRENT_SCHEMA_VERSION  # noqa: E402


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


def add_task(root: Path, *extra: str) -> str:
    r = run(
        [
            sys.executable,
            str(TASK),
            "add",
            "--next",
            "--story",
            "S-001",
            "--milestone",
            "M-001",
            "--title",
            "a task",
            "--commit-type",
            "feat",
            "--acceptance",
            "works",
            *extra,
        ],
        root,
    )
    return json.loads(r.stdout)["id"]


class TestSchemaMigration(unittest.TestCase):
    def test_init_stamps_current_version_and_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = new_project(Path(tmp))
            status = json.loads((plan / "status.json").read_text())
            self.assertEqual(status["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertTrue((plan / "issues.json").exists())

    def test_legacy_project_migrates_without_data_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            add_task(root)
            # Simulate a true v1 project: no schema_version, no registries.
            status = json.loads((plan / "status.json").read_text())
            del status["schema_version"]
            (plan / "status.json").write_text(json.dumps(status))
            (plan / "issues.json").unlink()
            (plan / "linked.json").unlink()

            run([sys.executable, str(MIGRATE)], root)

            migrated = json.loads((plan / "status.json").read_text())
            self.assertEqual(migrated["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertTrue((plan / "issues.json").exists())
            self.assertTrue((plan / "linked.json").exists())
            tasks = json.loads((plan / "tasks.json").read_text())["tasks"]
            self.assertEqual(len(tasks), 1)

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            before = (plan / "status.json").read_text()
            run([sys.executable, str(MIGRATE)], root)
            self.assertEqual((plan / "status.json").read_text(), before)

    def test_future_version_fails_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = new_project(root)
            status = json.loads((plan / "status.json").read_text())
            status["schema_version"] = CURRENT_SCHEMA_VERSION + 5
            (plan / "status.json").write_text(json.dumps(status))
            result = run([sys.executable, str(STATUS), "show"], root, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("newer than this Outfit supports", result.stderr)


class TestIssueRegistry(unittest.TestCase):
    def test_lifecycle_and_default_open_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            add_task(root)
            run(
                [sys.executable, str(ISSUE), "add", "--source-task", "T-001",
                 "--severity", "minor-defect", "--category", "tests",
                 "--description", "gap"],
                root,
            )
            run([sys.executable, str(ISSUE), "resolve", "I-001", "--by", "T-002"], root)
            listing = run([sys.executable, str(ISSUE), "list"], root).stdout
            self.assertIn("no issues", listing)
            all_listing = run([sys.executable, str(ISSUE), "list", "--all"], root).stdout
            self.assertIn("resolved", all_listing)

    def test_add_rejects_unknown_task_and_bad_severity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            r = run(
                [sys.executable, str(ISSUE), "add", "--source-task", "T-999",
                 "--severity", "minor-defect", "--category", "x", "--description", "y"],
                root, check=False,
            )
            self.assertNotEqual(r.returncode, 0)
            add_task(root)
            r = run(
                [sys.executable, str(ISSUE), "add", "--source-task", "T-001",
                 "--severity", "nope", "--category", "x", "--description", "y"],
                root, check=False,
            )
            self.assertNotEqual(r.returncode, 0)

    def test_resolve_rejects_non_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            add_task(root)
            run(
                [sys.executable, str(ISSUE), "add", "--source-task", "T-001",
                 "--severity", "major", "--category", "x", "--description", "y"],
                root,
            )
            run([sys.executable, str(ISSUE), "accept", "I-001", "--decision", "ok"], root)
            r = run([sys.executable, str(ISSUE), "resolve", "I-001"], root, check=False)
            self.assertNotEqual(r.returncode, 0)


class TestAtomicTaskIds(unittest.TestCase):
    def test_next_never_reuses_and_rejects_id_combo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new_project(root)
            self.assertEqual(add_task(root), "T-001")
            self.assertEqual(add_task(root), "T-002")
            # Cancel T-002; next id must not reuse it.
            run([sys.executable, str(TASK), "set-status", "T-002", "cancelled",
                 "--reason", "drop"], root)
            self.assertEqual(add_task(root), "T-003")
            r = run(
                [sys.executable, str(TASK), "add", "--id", "T-009", "--next",
                 "--story", "S-001", "--milestone", "M-001", "--title", "x",
                 "--commit-type", "feat", "--acceptance", "y"],
                root, check=False,
            )
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
