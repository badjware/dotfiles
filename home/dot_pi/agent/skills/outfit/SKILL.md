---
name: outfit
description: Runs a structured, multi-agent software project under a single user-facing lead. The lead drives discovery, planning, and execution phases, writes user stories so the user does not have to, and dispatches non-interactive worker agents (programmer, reviewer, QA) for individual tasks. Use whenever the user wants to build a new project or add a non-trivial feature to an existing project with planning, task tracking, and review/QA gates instead of ad-hoc coding.
---

# Outfit

A small mixed-role agent team under one lead. The user only ever talks to the lead. The lead orchestrates everyone else through files in `.plan/` and through the helper scripts under `scripts/`.

## Roles

- **lead** (this session, interactive): only user-facing agent. Runs discovery, planning, and execution phases. Sole writer of shared state (`plan.md`, `tasks.json`, `status.json`, `stories/`, `decisions.md`).
- **programmer** (non-interactive worker): implements one task, writes to `.plan/work/<task-id>/` and to project source code.
- **reviewer** (non-interactive worker, fresh context): reviews one completed task.
- **qa** (non-interactive worker, fresh context): writes and runs acceptance checks for one task.

Workers never talk to the user. Within `.plan/`, workers write only inside their own `work/<task-id>/` directory. Source code writes elsewhere in the project are unrestricted (subject to per-role scope rules).

## Workflow

1. **Bootstrap.** Ask the user whether this is a new project (greenfield) or a feature in an existing project. Then follow `bootstrap/greenfield.md` or `bootstrap/existing.md`.
2. **Discovery phase.** Lead acts as product owner: asks the user what they want, why, for whom, what success looks like. Writes user stories to `.plan/stories/`. Forbidden in this phase: writing tasks, decomposing into implementation, touching `tasks.json`.
3. **Planning phase.** Lead decomposes stories into milestones and tasks. Writes `plan.md` and populates `tasks.json` via `scripts/task.py add`. **Gate 1 (user approval)**: present the plan, wait for approval before any code is written.
4. **Execution phase.** For each task in dependency order, lead dispatches a programmer, then a reviewer, then a QA worker via `scripts/dispatch.py`. Lead drives task state via `scripts/task.py set-status` based on worker output. **Gate 2 (user approval)**: at the end of every milestone, present a milestone summary and wait for approval before starting the next milestone.
5. **Re-discovery.** Allowed any time the user introduces new requirements. Lead must declare "entering discovery phase" explicitly before doing PO work again.

## Phase discipline

The lead must declare the current phase at the start of every turn that performs work, e.g. `[phase: planning]`. Crossing phase boundaries without an explicit declaration is the main failure mode this skill exists to prevent.

## JSON state is script-only

`.plan/tasks.json` and `.plan/status.json` are **never** edited by hand by any agent, including the lead. All reads go through `scripts/task.py get|list` and `scripts/status.py show`; all writes go through `scripts/task.py {add|set-status|block}` and `scripts/status.py {set-phase|set-milestone|approve-gate-1|approve-milestone}`. The scripts enforce structural constraints (id formats, required fields, dependency existence and acyclicity) and the task-status state machine. If a script does not yet exist, the lead must stop and tell the user.

## Files this skill manages

```
.plan/
├── plan.md              # lead-owned: high-level plan, milestones
├── stories/
│   └── S-001-<slug>.md  # lead-owned: user stories
├── tasks.json           # lead-owned: structured task state (managed by scripts/task.py)
├── status.json          # lead-owned: current phase, milestone, gate status
├── decisions.md         # lead-owned: key decisions log (append-only)
└── work/
    └── T-007/           # worker-owned scratch per task
        ├── notes.md     # programmer scratch
        ├── review.md    # reviewer output
        ├── qa.md        # qa output
        └── status.md    # worker-reported status: done | blocked | needs-changes
```

The lead is the only writer of everything outside `work/`. Workers are the only writers inside `work/<their-task-id>/`.

## Entry point

Read `roles/lead.md` for the full lead instructions. Then ask the user: greenfield or existing project? Then follow the matching bootstrap file.

## Reference files

- `roles/lead.md` — full lead instructions, phase rules, dispatch loop
- `roles/programmer.md` — programmer worker prompt
- `roles/reviewer.md` — reviewer worker prompt
- `roles/qa.md` — qa worker prompt
- `bootstrap/greenfield.md` — new project bootstrap
- `bootstrap/existing.md` — existing project bootstrap
- `templates/plan.md` — plan.md template
- `templates/story.md` — user story template
