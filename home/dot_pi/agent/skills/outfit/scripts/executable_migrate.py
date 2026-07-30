#!/usr/bin/env python3
"""Idempotently migrate a .plan/ directory to the current state schema.

Migration only adds new metadata; it never deletes tasks, gates, reviews, or any
historical work artifact. Re-running against an already-current project makes no
changes. State written by a newer Outfit than this one fails safely.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    die,
    find_plan_dir,
    read_json,
    status_schema_version,
    write_issues,
    write_links,
    write_status,
)


def migrate(plan: Path, dry_run: bool) -> list[str]:
    """Return the list of changes applied (or that would apply on dry-run)."""
    status = read_json(plan / "status.json")
    if not isinstance(status, dict):
        die("status.json malformed")
    version = status_schema_version(status)
    if version > CURRENT_SCHEMA_VERSION:
        die(
            f"state schema_version {version} is newer than this Outfit supports "
            f"({CURRENT_SCHEMA_VERSION}); upgrade Outfit, do not downgrade state"
        )

    changes: list[str] = []

    # v1 -> v2: introduce explicit schema_version and the issue registry.
    if status.get("schema_version") != CURRENT_SCHEMA_VERSION:
        changes.append(
            f"set schema_version {status.get('schema_version', 1)} -> {CURRENT_SCHEMA_VERSION}"
        )
    if not (plan / "issues.json").exists():
        changes.append("create issues.json (empty registry)")
    # v3: linked-project handoff registry.
    if not (plan / "linked.json").exists():
        changes.append("create linked.json (empty registry)")

    if dry_run or not changes:
        return changes

    if not (plan / "issues.json").exists():
        write_issues(plan, {"issues": []})
    if not (plan / "linked.json").exists():
        write_links(plan, {"links": []})
    status["schema_version"] = CURRENT_SCHEMA_VERSION
    write_status(plan, status)
    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report needed changes without writing anything",
    )
    args = ap.parse_args()

    plan = find_plan_dir()
    changes = migrate(plan, args.dry_run)
    if not changes:
        print(f"already at schema_version {CURRENT_SCHEMA_VERSION}; no changes")
        return 0
    verb = "would apply" if args.dry_run else "applied"
    print(f"{verb} {len(changes)} change(s) (schema_version {CURRENT_SCHEMA_VERSION}):")
    for c in changes:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
