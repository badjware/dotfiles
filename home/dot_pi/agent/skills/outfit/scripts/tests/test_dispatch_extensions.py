#!/usr/bin/env python3
"""Verify Outfit workers start pi without extension discovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DISPATCH = Path(__file__).resolve().parent.parent / "dispatch.py"


class TestDispatchExtensions(unittest.TestCase):
    def test_all_worker_roles_disable_extensions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="outfit_dispatch_test_") as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=root, check=True
            )
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "chore: test baseline"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True
            ).stdout.strip()
            exclude = root / ".git" / "info" / "exclude"
            exclude.write_text(exclude.read_text() + "\n.plan/\n")

            plan = root / ".plan"
            (plan / "work").mkdir(parents=True)
            (plan / "tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "T-001",
                                "title": "test task",
                            }
                        ]
                    }
                )
            )
            # QA now reads recorded baselines from status.json (T-011/T-012).
            (plan / "status.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "phase": "execution",
                        "current_milestone": "M-001",
                        "gate_1_approved": True,
                        "milestone_gates": {},
                        "milestone_baselines": {"M-001": head},
                        "project_baseline": head,
                    }
                )
            )

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_pi = bin_dir / "pi"
            fake_pi.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "open(os.environ['PI_ARGS_FILE'], 'w').write(json.dumps(sys.argv[1:]))\n"
            )
            fake_pi.chmod(0o755)

            args_file = root / "pi-args.json"
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["PI_ARGS_FILE"] = str(args_file)

            for role, target in (
                ("programmer", "T-001"),
                ("reviewer", "T-001"),
                ("qa", "M-001"),
            ):
                with self.subTest(role=role):
                    result = subprocess.run(
                        [sys.executable, str(DISPATCH), role, target],
                        cwd=root,
                        env=env,
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("--no-extensions", json.loads(args_file.read_text()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
