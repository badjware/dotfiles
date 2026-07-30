#!/usr/bin/env python3
"""Final release audit (T-013).

Runs the deterministic, git- and dependency-level release checks that a script
can verify reproducibly. Project-specific test/build/vet/lint commands are the
QA worker's responsibility; this audit covers the mechanical release blockers:

  git status (clean working tree)
  git diff --check (no conflict markers / whitespace errors)
  local module replacements (go.mod `replace => <local path>`)
  workspace-relative dependencies (go.work, package.json file:/link: deps)
  dirty linked repositories (from a linked-projects manifest, if present)

Temporary local replacements are blockers unless --allow-local-replacements is
passed (release explicitly permits them). Results are machine-readable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    find_plan_dir,
    git_is_repo,
    git_run,
    git_working_tree_dirty,
    primary_repo_name,
    read_links,
    read_workspace,
    repo_dirty,
)


def _scan_go_mod_replacements(root: Path) -> list[str]:
    """Return 'path: replace directive' for each local go.mod replacement."""
    found: list[str] = []
    for mod in root.rglob("go.mod"):
        if ".plan" in mod.parts:
            continue
        for line in mod.read_text(errors="replace").splitlines():
            m = re.search(r"=>\s*(\S+)", line)
            if m and (m.group(1).startswith((".", "/"))):
                found.append(f"{mod.relative_to(root)}: {line.strip()}")
    return found


def _scan_workspace_deps(root: Path) -> list[str]:
    """Return workspace-relative dependency signals (go.work, file:/link: deps)."""
    signals: list[str] = []
    for work in root.rglob("go.work"):
        if ".plan" not in work.parts:
            signals.append(f"{work.relative_to(root)}: go workspace present")
    for pkg in root.rglob("package.json"):
        if ".plan" in pkg.parts or "node_modules" in pkg.parts:
            continue
        text = pkg.read_text(errors="replace")
        for m in re.finditer(r'"[^"]+"\s*:\s*"(file:|link:)[^"]*"', text):
            signals.append(f"{pkg.relative_to(root)}: {m.group(0)}")
    return signals


def run_audit(root: Path, allow_local_replacements: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Return (blockers, warnings, report_lines)."""
    blockers: list[str] = []
    warnings: list[str] = []
    report: list[str] = []

    dirty = git_working_tree_dirty(root)
    report.append(f"git status: {'DIRTY' if dirty else 'clean'}")
    if dirty:
        blockers.append("working tree has uncommitted project changes")

    # Every declared workspace repository must be clean (T-016).
    ws = read_workspace(root / ".plan")
    if ws is not None:
        primary = primary_repo_name(ws)
        report.append(f"workspace repositories: {len(ws['repositories'])}")
        for name, spec in ws["repositories"].items():
            if name == primary:
                continue  # covered by the primary git status above
            repo = (root / spec["path"]).resolve()
            if not repo.is_dir() or not git_is_repo(repo):
                report.append(f"  - {name} {spec['path']}: MISSING")
                blockers.append(f"workspace repository {name} ({spec['path']}) is missing")
            elif repo_dirty(repo, exclude_plan=False):
                report.append(f"  - {name} {spec['path']}: DIRTY")
                blockers.append(f"workspace repository {name} ({spec['path']}) has uncommitted changes")
            else:
                report.append(f"  - {name} {spec['path']}: clean")

    check = git_run(["diff", "--check"], root)
    if check.stdout.strip() or check.returncode != 0:
        report.append("git diff --check: FAILED")
        blockers.append("git diff --check reported conflict markers or whitespace errors")
    else:
        report.append("git diff --check: clean")

    replacements = _scan_go_mod_replacements(root)
    report.append(f"local module replacements: {len(replacements)}")
    for r in replacements:
        report.append(f"  - {r}")
    if replacements and not allow_local_replacements:
        blockers.append(
            f"{len(replacements)} local module replacement(s) present "
            "(pass --allow-local-replacements to permit for release)"
        )
    elif replacements:
        warnings.append(f"{len(replacements)} local module replacement(s) allowed for release")

    ws = _scan_workspace_deps(root)
    report.append(f"workspace-relative dependencies: {len(ws)}")
    for w in ws:
        report.append(f"  - {w}")
    if ws:
        warnings.append(f"{len(ws)} workspace-relative dependency signal(s)")

    # Dirty linked repositories and unreleased prerequisites (T-015).
    links = read_links(root / ".plan")["links"]
    report.append(f"linked repositories: {len(links)}")
    for link in links:
        repo = (root / link["repository"]).resolve()
        if not repo.is_dir() or not git_is_repo(repo):
            report.append(f"  - {link['id']} {link['repository']}: MISSING")
            blockers.append(f"linked repository {link['repository']} is missing")
            continue
        if git_run(["status", "--porcelain"], repo).stdout.strip():
            report.append(f"  - {link['id']} {link['repository']}: DIRTY ({repo})")
            blockers.append(f"linked repository {link['repository']} has a dirty working tree")
        if link.get("temporary_override"):
            report.append(f"  - {link['id']} {link['repository']}: temporary override active")
            blockers.append(f"temporary override for {link['id']} ({link['repository']}) remains")
        elif link["release_status"] != "released":
            report.append(f"  - {link['id']} {link['repository']}: release pending")
            blockers.append(f"linked prerequisite {link['id']} ({link['repository']}) is unreleased")

    return blockers, warnings, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--allow-local-replacements",
        action="store_true",
        help="permit local module replacements for this release",
    )
    args = ap.parse_args()

    plan = find_plan_dir()
    blockers, warnings, report = run_audit(plan.parent, args.allow_local_replacements)

    print("=== release audit ===")
    for line in report:
        print(line)
    if warnings:
        print("warnings:")
        for w in warnings:
            print(f"  - {w}")
    if blockers:
        print("BLOCKERS:")
        for b in blockers:
            print(f"  - {b}")
        return 1
    print("audit: no blockers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
