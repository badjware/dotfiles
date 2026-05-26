---
name: outfit
description: Runs a structured, multi-agent software project under a single user-facing lead. The lead drives discovery, planning, and execution phases, writes user stories so the user does not have to, and dispatches non-interactive worker agents (programmer, reviewer, QA) for individual tasks. Use whenever the user wants to build a new project or add a non-trivial feature to an existing project with planning, task tracking, and review/QA gates instead of ad-hoc coding.
---

# Outfit

A small mixed-role agent team under one lead. The user only ever talks to the lead. The lead orchestrates everyone else through files in `.plan/`, through the helper scripts under `scripts/`, and through git commits at named events.

## Roles

- **lead** (this session, interactive): only user-facing agent. Runs discovery, planning, and execution phases. Sole writer of shared state (`plan.md`, `tasks.json`, `status.json`, `stories/`, `decisions.md`) and sole committer.
- **programmer** (non-interactive worker): implements one task, writes to `.plan/work/<task-id>/` and to project source code. Does not commit. Maintains `.plan/codebase.md` with accumulated codebase knowledge.
- **reviewer** (non-interactive worker, fresh context): reviews one completed task using `git diff` against the dispatch baseline. Returns `done` (with any minor issues logged) or `needs-changes` (blocker/major only).
- **qa** (non-interactive worker, fresh context): verifies acceptance criteria from the outside.

Workers never talk to the user. Within `.plan/`, workers write only inside their own `work/<task-id>/` directory. Source code writes elsewhere in the project are unrestricted (subject to per-role scope rules).

## Workflow

1. **Bootstrap.** Run `scripts/detect-project.py` to classify the cwd as `greenfield`, `existing`, or `in-progress`. For `existing` or `in-progress`, proceed directly. For `greenfield`, confirm with the user before proceeding (it is the surprising result and the point of no return for `git init`). Then follow `bootstrap/greenfield.md` or `bootstrap/existing.md` (the latter also covers resuming an `in-progress` run). `plan-init.py` ensures the project is a git repo (running `git init` if needed) and refuses to start if an existing repo has a dirty working tree.
2. **Discovery phase.** Lead acts as product owner: asks the user what they want, why, for whom, what success looks like. Writes user stories to `.plan/stories/`. Forbidden in this phase: writing tasks, decomposing into implementation, touching `tasks.json`.
3. **Planning phase.** Lead decomposes stories into milestones and tasks. Writes `plan.md` and populates `tasks.json` via `scripts/task.py add`. Lead also records technology and constraint decisions in `decisions.md`, flagging any that require user input (credentials, library choices, deployment targets, etc.) so they can be resolved before execution. **Gate 1 (user approval)**: present the plan and pending user-input items, wait for approval before any code is written. Approval is recorded via `scripts/status.py approve-gate-1`, which atomically advances the phase to `execution` **and commits the plan**.
4. **Execution phase.** For each task in dependency order, lead dispatches a programmer → reviewer → QA worker. Reviewer returns `done` (minors logged) or `needs-changes` (blocker/major); on `needs-changes` the programmer is re-dispatched once with the review as context and may reject issues it disagrees with in `review-response.md`. `set-status <id> done` auto-commits the task. **Gate 2 (user approval)**: at the end of every milestone, lead presents a summary with accumulated minor issues and any programmer rejections; user decides which to schedule as cleanup tasks. Approval auto-commits the milestone.
5. **Returning to discovery.** Allowed any time the user introduces new requirements: lead runs `scripts/status.py set-phase discovery` and re-enters discovery mode. Existing stories, plan, and tasks are preserved; the lead updates them as needed. There is no separate "re-discovery" phase, just discovery again.

## Phase discipline

The lead must declare the current phase at the start of every turn that performs work, e.g. `[phase: planning]`. Crossing phase boundaries without an explicit declaration is the main failure mode this skill exists to prevent.

## JSON state is script-only

`.plan/tasks.json` and `.plan/status.json` are **never** edited or read directly by any agent, including the lead and the workers. All reads go through `scripts/task.py {get|list}` and `scripts/status.py show`; all writes go through `scripts/task.py {add|set-status|update}` and `scripts/status.py {set-phase|set-milestone|approve-gate-1|approve-milestone}`. The scripts enforce structural constraints (id formats, required fields, dependency existence and acyclicity), the task-status state machine, and phase transition guards. If a script does not yet exist, the lead must stop and tell the user.

## Git is required

The project lives in a git repo (created by `plan-init.py` if needed). The lead is the only committer and commits at named events (gate 1 approval, each task done, each milestone approval) via auto-commits triggered from `status.py` and `task.py`. Failed commits are fatal and revert the corresponding state change. Workers do not commit; their changes accumulate in the working tree until the lead commits the task.

Reviewers and QA workers see what changed via `git diff <baseline-sha>`, where the baseline is the project HEAD at dispatch time (recorded in `.plan/work/<task-id>/baseline-<role>.sha`).

## Files this skill manages

```
.plan/
├── plan.md              # lead-owned: high-level plan, milestones
├── stories/
│   └── S-001-<slug>.md  # lead-owned: user stories
├── tasks.json           # lead-owned: structured task state (managed by scripts/task.py)
├── status.json          # lead-owned: current phase, milestone, gate status
├── decisions.md         # lead-owned: key decisions log (append-only)
├── codebase.md          # programmer-maintained: codebase map (≤150 lines)
└── work/
    └── T-007/                  # worker-owned scratch per task
        ├── notes.md            # programmer scratch
        ├── review-response.md  # programmer's accepted/rejected per review issue (on rework)
        ├── review.md           # reviewer output
        ├── qa.md               # qa output
        ├── status-programmer.md  # done | blocked | needs-changes
        ├── status-reviewer.md
        ├── status-qa.md
        ├── baseline-<role>.sha   # git HEAD at dispatch time, per role
        ├── worker.log            # full transcript (gitignored)
        └── session-*/            # pi session per dispatch (gitignored)
```

The lead is the only writer of everything outside `work/`. Workers are the only writers inside `work/<their-task-id>/`.

## Entry point

Read `roles/lead.md` for the full lead instructions. Run `scripts/detect-project.py`, confirm with the user if `greenfield`, then follow `bootstrap/greenfield.md` or `bootstrap/existing.md`.

