#!/usr/bin/env python3
"""Global project status: phase, current milestone, gate approvals. Sole writer of .plan/status.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _state import (  # noqa: E402
    ID_MILESTONE_RE,
    PHASE_TRANSITIONS,
    PHASES,
    die,
    find_plan_dir,
    git_head_sha,
    read_links,
    read_status,
    read_tasks,
    write_status,
)
from audit import run_audit  # noqa: E402


def cmd_show(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    s = read_status(plan)
    tasks = read_tasks(plan)["tasks"]
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    blocked = [
        (t["id"], t.get("blocked_reason", ""))
        for t in tasks
        if t["status"] == "blocked"
    ]
    print(f"phase:             {s.get('phase')}")
    print(f"current_milestone: {s.get('current_milestone')}")
    print(f"gate_1_approved:   {s.get('gate_1_approved')}")
    gates = s.get("milestone_gates", {})
    if gates:
        print("milestone_gates:")
        for m, st in gates.items():
            print(f"  {m}: {st}")
    print("task counts:")
    for k in ("todo", "in_progress", "in_review", "done", "blocked", "cancelled"):
        if k in counts:
            print(f"  {k}: {counts[k]}")
    if blocked:
        print("blocked:")
        for tid, reason in blocked:
            print(f"  {tid}: {reason}")
    return 0


def cmd_set_phase(args: argparse.Namespace) -> int:
    if args.phase not in PHASES:
        die(f"phase must be one of {sorted(PHASES)}: {args.phase!r}")
    plan = find_plan_dir()
    s = read_status(plan)
    cur = s.get("phase")
    if args.phase == cur:
        die(f"phase is already {cur}")
    allowed = PHASE_TRANSITIONS.get(cur, set())
    if args.phase not in allowed:
        if cur == "planning" and args.phase == "execution":
            die(
                "cannot enter execution from planning via set-phase; use approve-gate-1",
                category="state",
            )
        if cur == "discovery" and args.phase == "planning":
            die(
                "cannot enter planning from discovery via set-phase; use approve-discovery",
                category="state",
            )
        die(
            f"invalid phase transition {cur} -> {args.phase}; allowed: {sorted(allowed) or 'none'}",
            category="state",
        )
    s["phase"] = args.phase
    note = ""
    # Returning to discovery means the plan may change; re-require gate 1.
    if args.phase == "discovery" and s.get("gate_1_approved"):
        s["gate_1_approved"] = False
        note = " (gate 1 reset; re-approve before resuming execution)"
    write_status(plan, s)
    print(f"phase: {args.phase}{note}")
    return 0


def cmd_set_milestone(args: argparse.Namespace) -> int:
    if not ID_MILESTONE_RE.match(args.milestone):
        die(f"milestone must match M-\\d{{3,}}: {args.milestone!r}")
    plan = find_plan_dir()
    s = read_status(plan)
    # ensure tasks exist for this milestone
    tasks = read_tasks(plan)["tasks"]
    if not any(t["milestone"] == args.milestone for t in tasks):
        die(f"no tasks reference milestone {args.milestone}; refusing to set")
    s["current_milestone"] = args.milestone
    # T-011: record the milestone's baseline at activation and never overwrite it,
    # so QA always diffs against the true milestone start.
    baselines = s.setdefault("milestone_baselines", {})
    note = ""
    if args.milestone not in baselines:
        head = git_head_sha(plan.parent)
        baselines[args.milestone] = head or ""
        note = f" (baseline {head or 'none'})"
    write_status(plan, s)
    print(f"current_milestone: {args.milestone}{note}")
    return 0


def cmd_approve_discovery(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    s = read_status(plan)
    if s.get("phase") != "discovery":
        die(f"approve-discovery requires discovery phase (current: {s.get('phase')})")
    story_files = list((plan / "stories").glob("S-*.md"))
    if not story_files:
        die(
            "no stories found in .plan/stories/; write at least one story before approving discovery"
        )
    s["phase"] = "planning"
    write_status(plan, s)
    print("discovery approved; phase: planning")
    return 0


def cmd_approve_gate_1(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    s = read_status(plan)
    if s.get("gate_1_approved"):
        die("gate 1 already approved")
    if s.get("phase") != "planning":
        die(
            f"gate 1 can only be approved during planning phase (current: {s.get('phase')})"
        )
    tasks = read_tasks(plan)["tasks"]
    if not tasks:
        die("cannot approve gate 1: no tasks defined")
    # T-014: every temporary override must have a finalization task.
    _require_finalization_tasks(plan, tasks)
    s["gate_1_approved"] = True
    s["phase"] = "execution"  # gate 1 atomically advances phase
    # T-012: the project QA baseline is the project start (gate 1 HEAD).
    if not s.get("project_baseline"):
        s["project_baseline"] = git_head_sha(plan.parent) or ""
    write_status(plan, s)
    print("gate 1 approved; phase: execution")
    return 0


def cmd_approve_milestone(args: argparse.Namespace) -> int:
    if not ID_MILESTONE_RE.match(args.milestone):
        die(f"milestone must match M-\\d{{3,}}: {args.milestone!r}")
    plan = find_plan_dir()
    s = read_status(plan)
    tasks = read_tasks(plan)["tasks"]
    ms_tasks = [t for t in tasks if t["milestone"] == args.milestone]
    if not ms_tasks:
        die(f"no tasks for milestone {args.milestone}")
    not_done = [t["id"] for t in ms_tasks if t["status"] not in ("done", "cancelled")]
    if not_done:
        die(f"cannot approve {args.milestone}: tasks not done or cancelled: {not_done}")
    gates = s.setdefault("milestone_gates", {})
    gates[args.milestone] = "approved"
    write_status(plan, s)
    print(f"milestone {args.milestone}: approved")
    return 0


def _require_finalization_tasks(plan, tasks: list[dict]) -> None:
    """Fail if a linked dependency with a temporary override has no live
    finalization task (T-014)."""
    links = read_links(plan)["links"]
    overrides = [link for link in links if link.get("temporary_override")]
    if not overrides:
        return
    live = [t for t in tasks if t["status"] != "cancelled"]
    for link in overrides:
        if not any(link["id"] in t.get("finalizes", []) for t in live):
            die(
                f"temporary override for {link['id']} ({link['repository']}) has no "
                f"finalization task; add one with task.py add --finalizes {link['id']}",
                category="state",
            )


def cmd_approve_project(args: argparse.Namespace) -> int:
    """Approve the whole project (T-012). Distinct from final-milestone approval:
    requires every milestone approved, a passing project QA, and a clean release
    audit (T-013). Refuses on any blocker."""
    plan = find_plan_dir()
    s = read_status(plan)
    tasks = read_tasks(plan)["tasks"]
    milestones = sorted({t["milestone"] for t in tasks})
    if not milestones:
        die("no milestones defined", category="state")
    gates = s.get("milestone_gates", {})
    unapproved = [m for m in milestones if gates.get(m) != "approved"]
    if unapproved:
        die(f"cannot approve project: milestones not approved: {unapproved}", category="state")

    # Project QA must have run and passed.
    qa_file = plan / "work" / "project" / "status-qa.md"
    if not qa_file.exists():
        die("project QA has not run; dispatch.py qa project first", category="state")
    lines = qa_file.read_text().strip().splitlines()
    first = lines[0].strip() if lines else ""
    if first != "done":
        die(f"project QA is not done (status: {first or 'empty'})", category="state")

    # T-014: no temporary override may remain at project approval.
    remaining = [
        link for link in read_links(plan)["links"] if link.get("temporary_override")
    ]
    if remaining:
        ids = ", ".join(f"{link['id']} ({link['repository']})" for link in remaining)
        die(
            f"cannot approve project: temporary dependency overrides remain: {ids}",
            category="state",
        )

    # Automatic release audit (T-013).
    blockers, warnings, report = run_audit(plan.parent, args.allow_local_replacements)
    print("=== release audit ===")
    for line in report:
        print(line)
    for w in warnings:
        print(f"warning: {w}")
    if blockers:
        for b in blockers:
            print(f"BLOCKER: {b}", file=sys.stderr)
        die("cannot approve project: release audit reported blockers", category="state")

    s["project_approved"] = True
    s["release_ready"] = True
    write_status(plan, s)
    print("project approved; release_ready: true")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="print current status")
    p_show.set_defaults(func=cmd_show)

    p_ph = sub.add_parser("set-phase", help="set current phase")
    p_ph.add_argument("phase")
    p_ph.set_defaults(func=cmd_set_phase)

    p_ms = sub.add_parser("set-milestone", help="set current milestone")
    p_ms.add_argument("milestone")
    p_ms.set_defaults(func=cmd_set_milestone)

    p_disc = sub.add_parser(
        "approve-discovery",
        help="approve stories and advance discovery -> planning (gate 0)",
    )
    p_disc.set_defaults(func=cmd_approve_discovery)

    p_g1 = sub.add_parser("approve-gate-1", help="record gate 1 approval")
    p_g1.set_defaults(func=cmd_approve_gate_1)

    p_am = sub.add_parser("approve-milestone", help="record milestone approval")
    p_am.add_argument("milestone")
    p_am.set_defaults(func=cmd_approve_milestone)

    p_ap = sub.add_parser(
        "approve-project",
        help="approve the whole project (runs release audit; requires project QA)",
    )
    p_ap.add_argument(
        "--allow-local-replacements",
        action="store_true",
        help="permit local module replacements for release",
    )
    p_ap.set_defaults(func=cmd_approve_project)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
