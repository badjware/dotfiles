#!/usr/bin/env python3
"""T-018: end-to-end workflow fixtures for the 14 canonical scenarios.

These run in temporary git repositories and drive the real scripts. Worker
dispatch (pi) is simulated by writing the artifacts a worker would produce
(code changes, review-NN.md, status-*.md), so the fixtures exercise commits,
baselines, issue state, reviews, and gates without external services.
"""

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
ISSUE = SCRIPTS / "issue.py"
LINKED = SCRIPTS / "linked.py"
WORKSPACE = SCRIPTS / "workspace.py"


def run(args, cwd, check=True) -> subprocess.CompletedProcess:
    r = subprocess.run([str(a) for a in args], cwd=cwd, text=True, capture_output=True)
    if check and r.returncode != 0:
        raise AssertionError(r.stderr or r.stdout)
    return r


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


def exec_project(root: Path, ntasks: int = 1) -> Path:
    make_repo(root)
    run([sys.executable, PLAN_INIT, "--dir", root], root)
    plan = root / ".plan"
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    for _ in range(ntasks):
        run([sys.executable, TASK, "add", "--next", "--story", "S-001",
             "--milestone", "M-001", "--title", "a task", "--commit-type", "feat",
             "--acceptance", "works"], root)
    run([sys.executable, STATUS, "approve-discovery"], root)
    run([sys.executable, STATUS, "set-milestone", "M-001"], root)
    run([sys.executable, STATUS, "approve-gate-1"], root)
    return plan


def exec_project_no_gate(root: Path) -> Path:
    """Init a project with a story but no tasks/gates yet (caller drives them)."""
    make_repo(root)
    run([sys.executable, PLAN_INIT, "--dir", root], root)
    plan = root / ".plan"
    (plan / "stories" / "S-001-test.md").write_text("# Story\n")
    return plan


def wd(plan: Path, tid: str) -> Path:
    p = Path(run([sys.executable, TASK, "work-dir", tid], plan.parent).stdout.strip())
    p.mkdir(parents=True, exist_ok=True)
    return p


def programmer_done(root: Path, plan: Path, tid: str, filename: str, content: str) -> None:
    run([sys.executable, TASK, "set-status", tid, "in_progress"], root)
    (root / filename).write_text(content)
    d = wd(plan, tid)
    (d / "notes.md").write_text("Changed: " + filename + "\n")
    (d / "status-programmer.md").write_text("done\n")


def reviewer(plan: Path, tid: str, cycle: int, status: str) -> None:
    d = wd(plan, tid)
    (d / f"review-{cycle:02d}.md").write_text(f"Findings: {status}\n")
    (d / "status-reviewer.md").write_text(status + "\n")


def human_review(plan: Path, tid: str, cycle: int, text: str) -> None:
    (wd(plan, tid) / f"human-review-{cycle:02d}.md").write_text(text + "\n")


class TestE2E(unittest.TestCase):
    def test_01_normal_single_review_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            programmer_done(root, plan, "T-001", "a.py", "x=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 1, "done")
            human_review(plan, "T-001", 1, "approve")
            run([sys.executable, TASK, "set-status", "T-001", "done"], root)
            self.assertEqual(git(root, "log", "-1", "--pretty=%s"), "feat: a task")
            self.assertTrue((wd(plan, "T-001") / "review-01.md").exists())

    def test_02_human_and_reviewer_feedback_combined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            programmer_done(root, plan, "T-001", "a.py", "x=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 1, "needs-changes")
            human_review(plan, "T-001", 1, "blocker: fix edge case")
            run([sys.executable, ISSUE, "add", "--source-task", "T-001", "--severity",
                 "major", "--category", "correctness", "--description", "edge case"], root)
            # rework -> new cycle
            run([sys.executable, TASK, "set-status", "T-001", "in_progress"], root)
            (root / "a.py").write_text("x=2\n")
            (wd(plan, "T-001") / "review-response-01.md").write_text("I-001 accepted\n")
            (wd(plan, "T-001") / "status-programmer.md").write_text("done\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 2, "done")
            human_review(plan, "T-001", 2, "approve")
            run([sys.executable, ISSUE, "resolve", "I-001", "--by", "T-001"], root)
            run([sys.executable, TASK, "set-status", "T-001", "done"], root)
            d = wd(plan, "T-001")
            self.assertTrue((d / "review-01.md").exists() and (d / "review-02.md").exists())

    def test_03_user_edits_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            programmer_done(root, plan, "T-001", "a.py", "x=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 1, "done")
            (root / "a.py").write_text("x=1\nuser=1\n")
            run([sys.executable, TASK, "user-edited", "T-001"], root)
            self.assertFalse((wd(plan, "T-001") / "status-reviewer.md").exists())
            reviewer(plan, "T-001", 2, "done")  # fresh review
            human_review(plan, "T-001", 2, "approve")
            run([sys.executable, TASK, "set-status", "T-001", "done"], root)
            self.assertIn("user=1", git(root, "show", "HEAD:a.py"))

    def test_04_user_edit_introduces_change_is_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            programmer_done(root, plan, "T-001", "a.py", "ok=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 1, "done")
            (root / "a.py").write_text("ok=1\nsyntax error(\n")
            run([sys.executable, TASK, "user-edited", "T-001"], root)
            t = json.loads(run([sys.executable, TASK, "get", "T-001"], root).stdout)
            self.assertFalse(t["user_edits"][0]["verified"])
            self.assertIn("syntax error(", (wd(plan, "T-001") / "user-edit-01.patch").read_text())

    def test_05_task_local_amendment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            run([sys.executable, TASK, "amend", "T-001", "--reason", "clarify",
                 "--acceptance", "works exactly"], root)
            t = json.loads(run([sys.executable, TASK, "get", "T-001"], root).stdout)
            self.assertEqual(t["acceptance"], ["works exactly"])
            self.assertEqual(len(t["amendments"]), 1)

    def test_06_repeated_rejection_of_one_issue_escalates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exec_project(root)
            run([sys.executable, ISSUE, "add", "--source-task", "T-001", "--severity",
                 "major", "--category", "correctness", "--description", "x"], root)
            run([sys.executable, ISSUE, "reject", "I-001", "--cycle", "1", "--rationale", "no"], root)
            out = run([sys.executable, ISSUE, "reject", "I-001", "--cycle", "2", "--rationale", "no"], root).stdout
            self.assertIn("ESCALATE", out)

    def test_07_three_unrelated_refinements_do_not_escalate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exec_project(root)
            for i in range(3):
                run([sys.executable, ISSUE, "add", "--source-task", "T-001", "--severity",
                     "major", "--category", "correctness", "--description", f"issue {i}"], root)
            for iid in ("I-001", "I-002", "I-003"):
                out = run([sys.executable, ISSUE, "attempt", iid], root).stdout
                self.assertNotIn("ESCALATE", out)

    def test_08_cleanup_task_resolves_older_minor_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root, ntasks=2)
            run([sys.executable, ISSUE, "add", "--source-task", "T-001", "--severity",
                 "minor-defect", "--category", "tests", "--description", "thin"], root)
            # later cleanup task resolves it
            run([sys.executable, ISSUE, "resolve", "I-001", "--by", "T-002",
                 "--decision", "added test"], root)
            self.assertIn("no issues", run([sys.executable, ISSUE, "list"], root).stdout)

    def test_09_milestone_qa_uses_start_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            base = json.loads((plan / "status.json").read_text())["milestone_baselines"]["M-001"]
            programmer_done(root, plan, "T-001", "a.py", "x=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 1, "done")
            human_review(plan, "T-001", 1, "ok")
            run([sys.executable, TASK, "set-status", "T-001", "done"], root)
            # baseline unchanged and is an ancestor of HEAD, so the diff is non-empty
            self.assertEqual(
                json.loads((plan / "status.json").read_text())["milestone_baselines"]["M-001"], base)
            self.assertNotEqual(base, git(root, "rev-parse", "HEAD"))

    def test_10_temporary_override_blocks_project_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "libcore").mkdir()
            make_repo(base / "libcore")
            req = git(base / "libcore", "rev-parse", "HEAD")
            consumer = base / "consumer"
            consumer.mkdir()
            plan = exec_project(consumer)  # one normal task, at execution
            programmer_done(consumer, plan, "T-001", "a.py", "x=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], consumer)
            reviewer(plan, "T-001", 1, "done")
            human_review(plan, "T-001", 1, "ok")
            run([sys.executable, TASK, "set-status", "T-001", "done"], consumer)
            run([sys.executable, STATUS, "approve-milestone", "M-001"], consumer)
            # A temporary override discovered after the milestone is a backstop:
            # project approval must still refuse while it remains.
            run([sys.executable, LINKED, "add", "--repository", "../libcore",
                 "--required-commit", req, "--temporary-override", "../libcore"], consumer)
            (plan / "work" / "project").mkdir(parents=True)
            (plan / "work" / "project" / "status-qa.md").write_text("done\n")
            r = run([sys.executable, STATUS, "approve-project"], consumer, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("temporary dependency overrides remain", r.stderr)

    def test_11_linked_release_unblocks_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "libcore").mkdir()
            make_repo(base / "libcore")
            req = git(base / "libcore", "rev-parse", "HEAD")
            (base / "libcore" / "f.txt").write_text("v2\n")
            git(base / "libcore", "commit", "-am", "feat: v2")
            released = git(base / "libcore", "rev-parse", "HEAD")
            consumer = base / "consumer"
            consumer.mkdir()
            plan = exec_project_no_gate(consumer)
            run([sys.executable, LINKED, "add", "--repository", "../libcore",
                 "--required-commit", req, "--temporary-override", "../libcore"], consumer)
            run([sys.executable, TASK, "add", "--next", "--story", "S-001",
                 "--milestone", "M-001", "--title", "finalize", "--commit-type", "chore",
                 "--acceptance", "done", "--finalizes", "L-001"], consumer)
            run([sys.executable, STATUS, "approve-discovery"], consumer)
            run([sys.executable, STATUS, "set-milestone", "M-001"], consumer)
            run([sys.executable, STATUS, "approve-gate-1"], consumer)
            run([sys.executable, TASK, "set-status", "T-001", "in_progress"], consumer)
            (consumer / "c.txt").write_text("consume released\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], consumer)
            blocked = run([sys.executable, TASK, "set-status", "T-001", "done"], consumer, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            run([sys.executable, LINKED, "set-released", "--id", "L-001", "--version", released], consumer)
            run([sys.executable, TASK, "set-status", "T-001", "done"], consumer)

    def test_12_multi_repository_milestone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "libcore").mkdir()
            make_repo(base / "libcore")
            consumer = base / "consumer"
            consumer.mkdir()
            plan = exec_project_no_gate(consumer)
            run([sys.executable, WORKSPACE, "add", "--name", "consumer", "--path", "."], consumer)
            run([sys.executable, WORKSPACE, "add", "--name", "libcore", "--path", "../libcore"], consumer)
            run([sys.executable, TASK, "add", "--next", "--story", "S-001", "--milestone",
                 "M-001", "--title", "consumer work", "--commit-type", "feat", "--acceptance", "a"], consumer)
            run([sys.executable, TASK, "add", "--next", "--story", "S-001", "--milestone",
                 "M-001", "--title", "libcore work", "--commit-type", "feat", "--acceptance", "a",
                 "--repository", "libcore"], consumer)
            run([sys.executable, STATUS, "approve-discovery"], consumer)
            run([sys.executable, STATUS, "set-milestone", "M-001"], consumer)
            run([sys.executable, STATUS, "approve-gate-1"], consumer)
            # consumer task
            run([sys.executable, TASK, "set-status", "T-001", "in_progress"], consumer)
            (consumer / "c.txt").write_text("c\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], consumer)
            run([sys.executable, TASK, "set-status", "T-001", "done"], consumer)
            # libcore task
            run([sys.executable, TASK, "set-status", "T-002", "in_progress"], consumer)
            (base / "libcore" / "g.txt").write_text("g\n")
            run([sys.executable, TASK, "set-status", "T-002", "in_review"], consumer)
            run([sys.executable, TASK, "set-status", "T-002", "done"], consumer)
            self.assertEqual(git(consumer, "log", "-1", "--pretty=%s"), "feat: consumer work")
            self.assertEqual(git(base / "libcore", "log", "-1", "--pretty=%s"), "feat: libcore work")

    def test_13_resume_reads_active_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = exec_project(root)
            programmer_done(root, plan, "T-001", "a.py", "x=1\n")
            run([sys.executable, TASK, "set-status", "T-001", "in_review"], root)
            reviewer(plan, "T-001", 1, "needs-changes")
            run([sys.executable, ISSUE, "add", "--source-task", "T-001", "--severity",
                 "major", "--category", "correctness", "--description", "x"], root)
            out = run([sys.executable, TASK, "review-state", "T-001"], root).stdout
            self.assertIn("latest_cycle:  1", out)
            self.assertIn("open_issues:   1", out)

    def test_14_readonly_typo_vs_state_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exec_project(root)
            usage = run([sys.executable, TASK, "get", "T-999"], root, check=False)
            state = run([sys.executable, TASK, "set-status", "T-001", "done"], root, check=False)
            self.assertEqual(usage.returncode, 2)   # recoverable usage mistake
            self.assertEqual(state.returncode, 1)   # fatal invalid state transition


if __name__ == "__main__":
    unittest.main(verbosity=2)
