#!/usr/bin/env python3
"""Initialize .plan/ in the current directory.

Refuses to clobber an existing .plan/ directory.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import atomic_write_json, die, skill_dir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=".", help="project directory (default: cwd)")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    plan = root / ".plan"
    if plan.exists():
        die(f"{plan} already exists; refusing to clobber")

    (plan / "stories").mkdir(parents=True)
    (plan / "work").mkdir()

    # plan.md from template
    template_plan = (skill_dir() / "templates" / "plan.md").read_text()
    (plan / "plan.md").write_text(template_plan)

    # decisions.md header
    (plan / "decisions.md").write_text("# Decisions\n\n<!-- Append-only log of project decisions. Newest at the bottom. -->\n")

    # tasks.json
    atomic_write_json(plan / "tasks.json", {"tasks": []})

    # status.json
    atomic_write_json(plan / "status.json", {
        "phase": "discovery",
        "current_milestone": None,
        "gate_1_approved": False,
        "milestone_gates": {},
    })

    print(f"initialized {plan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
