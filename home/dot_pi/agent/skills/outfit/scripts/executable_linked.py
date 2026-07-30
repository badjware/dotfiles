#!/usr/bin/env python3
"""Linked-project handoff registry. Sole writer of .plan/linked.json.

Tracks a cross-repository prerequisite the current project depends on: the
linked repository path, the required commit, its release state, and whether the
consumer currently relies on a temporary local override. Resuming a paused
consumer validates that the released version actually contains the required
commit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    ID_LINK_RE,
    die,
    find_plan_dir,
    git_is_ancestor,
    git_is_repo,
    git_run,
    link_by_id,
    next_link_id,
    read_links,
    write_links,
)


def _resolve_repo(plan: Path, repository: str) -> Path:
    """Resolve a linked repository path relative to the consumer project root."""
    root = plan.parent
    p = (root / repository).resolve()
    if not p.is_dir() or not git_is_repo(p):
        die(f"linked repository is not a git repo: {repository} ({p})", category="state")
    return p


def _linked_repo_dirty(repo: Path) -> bool:
    r = git_run(["status", "--porcelain"], repo)
    return bool(r.stdout.strip())


def cmd_add(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    _resolve_repo(plan, args.repository)
    data = read_links(plan)
    links = data["links"]
    lid = next_link_id(links)
    link = {
        "id": lid,
        "repository": args.repository,
        "required_commit": args.required_commit,
        "release_status": "pending",
        "consumer": args.consumer,
        "temporary_override": args.temporary_override,
        "required_version": None,
    }
    links.append(link)
    write_links(plan, data)
    print(json.dumps(link, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    links = read_links(plan)["links"]
    if not links:
        print("(no linked projects)")
        return 0
    for link in links:
        override = f" override={link['temporary_override']}" if link.get("temporary_override") else ""
        ver = link.get("required_version") or "-"
        print(
            f"{link['id']}  {link['release_status']:<8}  {link['repository']}  "
            f"req={link['required_commit'][:12]}  version={ver}{override}"
        )
    return 0


def cmd_set_released(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    if not ID_LINK_RE.match(args.id):
        die(f"link id must match L-\\d{{3,}}: {args.id!r}")
    data = read_links(plan)
    link = link_by_id(data["links"], args.id)
    if not link:
        die(f"no link {args.id}")
    repo = _resolve_repo(plan, link["repository"])
    # The released version must contain the required commit.
    if not git_is_ancestor(repo, link["required_commit"], args.version):
        die(
            f"released version {args.version} does not contain required commit "
            f"{link['required_commit'][:12]} in {link['repository']}",
            category="state",
        )
    link["release_status"] = "released"
    link["required_version"] = args.version
    # A released dependency no longer needs a temporary override.
    link["temporary_override"] = None
    write_links(plan, data)
    print(f"{args.id}: released ({args.version}); temporary_override cleared")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    links = read_links(plan)["links"]
    if not links:
        print("(no linked projects)")
        return 0
    problems = 0
    for link in links:
        repo = (plan.parent / link["repository"]).resolve()
        prefix = f"{link['id']} {link['repository']}"
        if not repo.is_dir() or not git_is_repo(repo):
            print(f"{prefix}: MISSING repository")
            problems += 1
            continue
        if _linked_repo_dirty(repo):
            print(f"{prefix}: DIRTY working tree ({repo})")
            problems += 1
        if link["release_status"] == "released":
            if not git_is_ancestor(repo, link["required_commit"], link["required_version"]):
                print(
                    f"{prefix}: released version {link['required_version']} no longer "
                    f"contains required commit {link['required_commit'][:12]}"
                )
                problems += 1
            else:
                print(f"{prefix}: released, required commit present")
        else:
            print(f"{prefix}: PENDING release (required commit {link['required_commit'][:12]})")
            problems += 1
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="register a linked-project prerequisite")
    p_add.add_argument("--repository", required=True, help="path to the linked repo, e.g. ../libcore")
    p_add.add_argument("--required-commit", required=True, help="commit the consumer needs")
    p_add.add_argument("--consumer", default=".", help="consumer repo path (default: .)")
    p_add.add_argument(
        "--temporary-override",
        help="path of a temporary local override the consumer currently relies on",
    )
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list linked projects")
    p_list.set_defaults(func=cmd_list)

    p_rel = sub.add_parser(
        "set-released",
        help="mark a link released after validating the version contains the required commit",
    )
    p_rel.add_argument("--id", required=True)
    p_rel.add_argument("--version", required=True, help="released ref/tag/sha in the linked repo")
    p_rel.set_defaults(func=cmd_set_released)

    p_val = sub.add_parser(
        "validate",
        help="validate every link (dirty tree, pending release, commit containment)",
    )
    p_val.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
