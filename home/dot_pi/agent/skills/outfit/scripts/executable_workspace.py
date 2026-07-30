#!/usr/bin/env python3
"""Multi-repository workspace manifest. Sole writer of .plan/workspace.json.

A workspace lets one Outfit plan coordinate tasks across several git
repositories. The primary repository (path '.') hosts .plan/. Absence of a
manifest means a classic single-repository project, which behaves unchanged.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    die,
    find_plan_dir,
    git_is_repo,
    primary_repo_name,
    read_workspace,
    write_workspace,
)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def cmd_add(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    if not NAME_RE.fullmatch(args.name):
        die("name must be lowercase alphanumeric with . _ -")
    repo = (plan.parent / args.path).resolve()
    if not repo.is_dir() or not git_is_repo(repo):
        die(f"path is not a git repository: {args.path} ({repo})", category="state")
    ws = read_workspace(plan) or {"repositories": {}}
    repos = ws["repositories"]
    if args.name in repos:
        die(f"repository {args.name!r} already declared")
    # The first repo added should be the primary at '.'.
    if not repos and args.path not in (".", "./"):
        die("the first workspace repository must be the primary at path '.'")
    if args.path in (".", "./") and any(
        s["path"] in (".", "./") for s in repos.values()
    ):
        die("a primary repository (path '.') is already declared")
    repos[args.name] = {"path": args.path}
    write_workspace(plan, ws)
    print(f"added repository {args.name} -> {args.path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    ws = read_workspace(plan)
    if ws is None:
        print("(single-repository project; no workspace manifest)")
        return 0
    primary = primary_repo_name(ws)
    for name, spec in ws["repositories"].items():
        tag = "  (primary)" if name == primary else ""
        print(f"{name}: {spec['path']}{tag}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="declare a repository in the workspace")
    p_add.add_argument("--name", required=True, help="short repo name, e.g. libcore")
    p_add.add_argument("--path", required=True, help="path relative to project root, e.g. ../libcore or .")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list workspace repositories")
    p_list.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
