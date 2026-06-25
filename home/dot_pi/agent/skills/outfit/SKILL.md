---
name: outfit
description: Runs a structured, multi-agent software project under a single user-facing lead. The lead drives discovery, planning, and execution phases, writes user stories so the user does not have to, and dispatches non-interactive worker agents (programmer, reviewer, QA) for individual tasks. Use whenever the user wants to build a new project or add a non-trivial feature to an existing project with planning, task tracking, and review/QA gates instead of ad-hoc coding.
---

# Outfit

A small mixed-role agent team under one lead. The user only ever talks to the lead. The lead orchestrates everyone else through files in `.plan/`, through the helper scripts under `scripts/`, and through git commits at named events.

## Roles

- **lead** (this session, interactive): only user-facing agent. Runs discovery, planning, and execution phases. Sole writer of shared state (`plan.md`, `tasks.json`, `status.json`, `stories/`, `decisions.md`) and sole committer. Conducts human reviews interactively during task execution.
- **programmer** (non-interactive worker): implements one task, writes to `.plan/work/<task-id>/` and to project source code. Does not commit. Maintains `.plan/codebase.md` with accumulated codebase knowledge.
- **reviewer** (non-interactive worker, fresh context): reviews one completed task using `git diff` against the dispatch baseline. Returns `done` (with any minor issues logged) or `needs-changes` (blocker/major only). Runs concurrently with human review.
- **qa** (non-interactive worker, fresh context): verifies milestone-level acceptance criteria from the outside, testing cumulative changes at the end of each milestone before gate approval.

Workers never talk to the user. Within `.plan/`, workers write only inside their own `work/<task-id>/` directory. Source code writes elsewhere in the project are unrestricted (subject to per-role scope rules).

## Workflow

1. **Bootstrap.** Run `./scripts/detect-project.py` to classify the cwd as `greenfield`, `existing`, or `in-progress`. For `existing` or `in-progress`, proceed directly. For `greenfield`, confirm with the user before proceeding (it is the surprising result and the point of no return for `git init`). Follow the matching bootstrap file: `bootstrap/greenfield.md`, `bootstrap/existing.md`, or `bootstrap/resume.md`. `plan-init.py` ensures the project is a git repo (running `git init` if needed) and refuses to start if an existing repo has a dirty working tree.
2. **Discovery phase.** Lead acts as product owner: asks the user what they want, why, for whom, what success looks like. Writes user stories to `.plan/stories/`. Forbidden in this phase: writing tasks, decomposing into implementation, touching `tasks.json`. **Gate 0 (discovery approval)**: once stories are confirmed by the user, run `./scripts/status.py approve-discovery`, which commits stories and decisions.md and advances phase to `planning` atomically.
3. **Planning phase.** Lead decomposes stories into milestones and tasks. Writes `plan.md` and populates `tasks.json` via `./scripts/task.py add`. Milestone IDs follow the format `M-001`, `M-002`, etc. Lead also records technology and constraint decisions in `decisions.md`, flagging any that require user input (credentials, library choices, deployment targets, etc.) so they can be resolved before execution. Before Gate 1, the lead may offer to stress-test the plan with the user using the `grill-me` skill (particularly useful for non-trivial architectural choices, unfamiliar codebases, or fragile dependency graphs). **Gate 1 (user approval)**: present the plan and pending user-input items, wait for approval before any code is written. Approval is recorded via `./scripts/status.py approve-gate-1`, which atomically advances the phase to `execution` **and commits the plan**.
4. **Execution phase.** For each task in dependency order, lead dispatches a programmer, then conducts concurrent agent + human review. Agent reviewer is dispatched via worker; in parallel, the lead eagerly invites the user to review (providing the baseline SHA so they can `git diff` themselves) while the agent reviewer runs, then formally collects their feedback once the agent reviewer returns (recorded in `.plan/work/<task-id>/human-review.md`). If either review returns `needs-changes`, programmer is re-dispatched once with combined feedback; programmer may reject issues it disagrees with in `review-response.md`. Task is committed when both reviews approve. **Milestone QA:** at the end of every milestone, lead dispatches the QA worker to verify cumulative changes against milestone acceptance criteria. **Gate 2 (user approval)**: lead presents a summary with QA findings, accumulated minor issues, and any programmer rejections; user decides which to schedule as cleanup tasks. Approval auto-commits the milestone.
5. **Returning to discovery.** Allowed any time the user introduces new requirements: lead runs `./scripts/status.py set-phase discovery` and re-enters discovery mode. Existing stories, plan, and tasks are preserved; the lead updates them as needed. There is no separate "re-discovery" phase, just discovery again.

## Phase discipline

The lead must declare the current phase at the start of every turn that performs work, e.g. `[phase: planning]`. Crossing phase boundaries without an explicit declaration is the main failure mode this skill exists to prevent.

## JSON state is script-only

`.plan/tasks.json` and `.plan/status.json` are **never** edited or read directly by any agent, including the lead and the workers. All reads go through `./scripts/task.py {get|list}` and `./scripts/status.py show`; all writes go through `./scripts/task.py {add|set-status|update}` and `./scripts/status.py {set-phase|set-milestone|approve-gate-1|approve-milestone}`. The scripts enforce structural constraints (id formats, required fields, dependency existence and acyclicity), the task-status state machine, and phase transition guards. If a script does not yet exist, the lead must stop and tell the user.

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
├── codebase.md          # programmer-maintained: codebase map
└── work/
    ├── T-007-implement-login/   # task-level worker scratch (slug derived from title)
    │   ├── notes.md             # programmer scratch
    │   ├── rework-context.md    # combined reviewer+human feedback written by dispatch.py (on rework)
    │   ├── review-response.md   # programmer's accepted/rejected per review issue (on rework)
    │   ├── review.md            # agent reviewer output
    │   ├── human-review.md      # lead-recorded human review feedback
    │   ├── deferred-issues.md   # minor issues logged but not blocking (optional)
    │   ├── status-programmer.md # done | blocked | needs-changes
    │   ├── status-reviewer.md
    │   ├── baseline-<role>.sha  # git HEAD at dispatch time, per role
    │   └── session-<role>-<ts>/ # pi session per dispatch (gitignored)
    │       ├── output.log       # raw worker output
    │       └── metadata.json    # role, model, baseline, timing, exit_code
    └── M-001/                   # milestone-level QA scratch
        ├── qa.md                # qa output
        ├── status-qa.md
        ├── baseline-qa.sha
        └── session-qa-<ts>/     # gitignored
```

The lead is the only writer of everything outside `work/`. Workers are the only writers inside `work/<their-task-id>/`.

## Entry point

Read `roles/lead.md` for the full lead instructions. Run `./scripts/detect-project.py`, confirm with the user if `greenfield`, then follow the matching bootstrap file: `bootstrap/greenfield.md`, `bootstrap/existing.md`, or `bootstrap/resume.md`.
