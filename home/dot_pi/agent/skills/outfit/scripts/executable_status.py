#!/usr/bin/env python3
"""Global project status: phase, current milestone, gate approvals. Sole writer of .plan/status.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state import (  # noqa: E402
    GitError, ID_MILESTONE_RE, PHASE_TRANSITIONS, PHASES, die, find_plan_dir,
    git_commit_all, read_status, read_tasks, write_status,
)


def cmd_show(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    s = read_status(plan)
    tasks = read_tasks(plan)["tasks"]
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    blocked = [(t["id"], t.get("blocked_reason", "")) for t in tasks if t["status"] == "blocked"]
    print(f"phase:             {s.get('phase')}")
    print(f"current_milestone: {s.get('current_milestone')}")
    print(f"gate_1_approved:   {s.get('gate_1_approved')}")
    gates = s.get("milestone_gates", {})
    if gates:
        print("milestone_gates:")
        for m, st in gates.items():
            print(f"  {m}: {st}")
    print("task counts:")
    for k in ("todo", "in_progress", "in_review", "in_qa", "done", "blocked", "cancelled"):
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
        # Special-case the most likely confusion: trying to enter execution from planning.
        if cur == "planning" and args.phase == "execution":
            die("cannot enter execution from planning via set-phase; use approve-gate-1")
        die(f"invalid phase transition {cur} -> {args.phase}; allowed: {sorted(allowed) or 'none'}")
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
        die(f"milestone must match M\\d+: {args.milestone!r}")
    plan = find_plan_dir()
    s = read_status(plan)
    # ensure tasks exist for this milestone
    tasks = read_tasks(plan)["tasks"]
    if not any(t["milestone"] == args.milestone for t in tasks):
        die(f"no tasks reference milestone {args.milestone}; refusing to set")
    s["current_milestone"] = args.milestone
    write_status(plan, s)
    print(f"current_milestone: {args.milestone}")
    return 0


def cmd_approve_gate_1(args: argparse.Namespace) -> int:
    plan = find_plan_dir()
    s = read_status(plan)
    if s.get("gate_1_approved"):
        die("gate 1 already approved")
    if s.get("phase") != "planning":
        die(f"gate 1 can only be approved during planning phase (current: {s.get('phase')})")
    tasks = read_tasks(plan)["tasks"]
    if not tasks:
        die("cannot approve gate 1: no tasks defined")
    s["gate_1_approved"] = True
    s["phase"] = "execution"  # gate 1 atomically advances phase
    write_status(plan, s)
    try:
        git_commit_all(plan.parent, "outfit: plan approved (gate 1)")
    except GitError as e:
        s["gate_1_approved"] = False
        s["phase"] = "planning"
        write_status(plan, s)
        die(f"commit failed (state reverted): {e}")
    print("gate 1 approved; phase: execution")
    return 0


def cmd_approve_milestone(args: argparse.Namespace) -> int:
    if not ID_MILESTONE_RE.match(args.milestone):
        die(f"milestone must match M\\d+: {args.milestone!r}")
    plan = find_plan_dir()
    s = read_status(plan)
    tasks = read_tasks(plan)["tasks"]
    ms_tasks = [t for t in tasks if t["milestone"] == args.milestone]
    if not ms_tasks:
        die(f"no tasks for milestone {args.milestone}")
    not_done = [t["id"] for t in ms_tasks if t["status"] != "done"]
    if not_done:
        die(f"cannot approve {args.milestone}: tasks not done: {not_done}")
    gates = s.setdefault("milestone_gates", {})
    prior = gates.get(args.milestone)
    gates[args.milestone] = "approved"
    write_status(plan, s)
    try:
        git_commit_all(plan.parent, f"outfit: milestone {args.milestone} approved")
    except GitError as e:
        if prior is None:
            del gates[args.milestone]
        else:
            gates[args.milestone] = prior
        write_status(plan, s)
        die(f"commit failed (state reverted): {e}")
    print(f"milestone {args.milestone}: approved")
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

    p_g1 = sub.add_parser("approve-gate-1", help="record gate 1 approval")
    p_g1.set_defaults(func=cmd_approve_gate_1)

    p_am = sub.add_parser("approve-milestone", help="record milestone approval")
    p_am.add_argument("milestone")
    p_am.set_defaults(func=cmd_approve_milestone)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
