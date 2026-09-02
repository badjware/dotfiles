---
name: outfit
description: Runs a structured, multi-agent software project under a single user-facing lead. The lead drives discovery, planning, and execution phases, writes user stories so the user does not have to, and dispatches non-interactive worker agents (programmer, reviewer, QA) for individual tasks. Use whenever the user wants to build a new project or add a non-trivial feature to an existing project with planning, task tracking, and review/QA gates instead of ad-hoc coding.
version: 1
updated: "2026-09-01"
compatibility: "Requires pi, git, and python3."
---

# Outfit

A small mixed-role agent team under one lead. The user only ever talks to the lead. The lead orchestrates everyone else through local files in `.plan/` and the helper scripts under `scripts/`. Outfit never commits `.plan/` and never modifies project `.gitignore` files.

## Roles

- **lead** (this session, interactive): only user-facing agent. Runs discovery, planning, and execution phases. Sole writer of shared state (`plan.md`, `tasks.json`, `status.json`, `stories/`, `decisions.md`) and sole committer. Conducts human reviews interactively during task execution.
- **programmer** (non-interactive worker): implements one task, writes to `.plan/work/<task-id>/` and to project source code. Does not commit. Maintains `.plan/codebase.md` with accumulated codebase knowledge.
- **reviewer** (non-interactive worker, fresh context): reviews one completed task using `git diff` against the dispatch baseline. Returns `done` (with any minor issues logged) or `needs-changes` (blocker/major only). Runs concurrently with human review.
- **qa** (non-interactive worker, fresh context): verifies milestone-level acceptance criteria from the outside, testing cumulative changes at the end of each milestone before gate approval.

Workers never talk to the user. Within `.plan/`, workers write only inside their own `work/<task-id>/` directory. Source code writes elsewhere in the project are unrestricted (subject to per-role scope rules).

## Workflow

1. **Bootstrap.** Run `./scripts/detect-project.py` to classify the cwd as `greenfield`, `existing`, or `in-progress`. For `existing` or `in-progress`, proceed directly. For `greenfield`, confirm with the user before proceeding (it is the surprising result and the point of no return for `git init`). Follow the matching bootstrap file: `bootstrap/greenfield.md`, `bootstrap/existing.md`, or `bootstrap/resume.md`. `plan-init.py` ensures the project is a git repo (running `git init` if needed) and refuses to start if an existing repo has a dirty working tree.
2. **Discovery phase.** Lead acts as product owner: asks the user what they want, why, for whom, what success looks like. Writes user stories to `.plan/stories/`. Forbidden in this phase: writing tasks, decomposing into implementation, touching `tasks.json`. **Gate 0 (discovery approval)**: once stories are confirmed by the user, run `./scripts/status.py approve-discovery`, which advances local state to `planning`.
3. **Planning phase.** Lead decomposes stories into milestones and tasks. Writes `plan.md` and populates `tasks.json` via `./scripts/task.py add`, including a required Conventional Commit type and optional scope for every task. Milestone IDs follow the format `M-001`, `M-002`, etc. Lead also records technology and constraint decisions in `decisions.md`, flagging any that require user input (credentials, library choices, deployment targets, etc.) so they can be resolved before execution. Before Gate 1, the lead may offer to stress-test the plan with the user using the `grill-me` skill (particularly useful for non-trivial architectural choices, unfamiliar codebases, or fragile dependency graphs). **Gate 1 (user approval)**: present the plan and pending user-input items, wait for approval before any code is written. Approval is recorded locally via `./scripts/status.py approve-gate-1`, which advances the phase to `execution`.
4. **Execution phase.** For each task in dependency order, lead dispatches a programmer, then conducts concurrent agent + human review. Agent reviewer is dispatched via worker; in parallel, the lead eagerly invites the user to review (providing the baseline SHA so they can `git diff` themselves) while the agent reviewer runs, then formally collects their feedback once the agent reviewer returns (recorded in `.plan/work/<task-id>/human-review-NN.md`, one immutable file per cycle). Reviewers classify findings (blocker/major/minor-defect/optional-enhancement/observation) and the lead records them in the issue registry with stable IDs. If either review has a blocker or major finding, the programmer is re-dispatched with combined feedback; it records per-issue accepted/rejected decisions in `review-response-NN.md`. Rework attempts are tracked per issue ID and escalate at a limit. Direct user edits during review are checkpointed via `task.py user-edited`, which marks the reviewer approval stale and forces re-verification and a fresh reviewer. Project changes are committed with the task's Conventional Commit metadata when both reviews approve. **Milestone QA:** at the end of every milestone, lead dispatches the QA worker to verify cumulative changes against the recorded milestone-start baseline. **Gate 2 (user approval)**: lead presents a summary with QA findings and the open issue registry; user decides which to schedule as cleanup tasks. Approval updates local state without creating an empty commit. **Project completion:** after the final milestone, the lead runs whole-project QA (`dispatch.py qa project`) and `status.py approve-project`, which runs an automatic release audit (`scripts/audit.py`) and refuses on any blocker. Feature-complete (all milestones approved) is distinct from release-ready (project QA passed, audit clean).
5. **Returning to discovery.** Allowed any time the user introduces new requirements: lead runs `./scripts/status.py set-phase discovery` and re-enters discovery mode. Existing stories, plan, and tasks are preserved; the lead updates them as needed. There is no separate "re-discovery" phase, just discovery again.

## Phase discipline

The lead must declare the current phase at the start of every turn that performs work, e.g. `[phase: planning]`. Crossing phase boundaries without an explicit declaration is the main failure mode this skill exists to prevent.

## JSON state is script-only

`.plan/tasks.json`, `.plan/status.json`, and `.plan/issues.json` are **never** edited or read directly by any agent, including the lead and the workers. All reads go through `./scripts/task.py {get|list|review-state}`, `./scripts/status.py show`, and `./scripts/issue.py list`; all writes go through `./scripts/task.py {add|set-status|update}`, `./scripts/status.py {set-phase|set-milestone|approve-gate-1|approve-milestone|approve-project}`, and `./scripts/issue.py {add|resolve|accept|supersede}`. `status.py set-milestone` records the milestone-start baseline for QA; `status.py approve-project` runs the automatic release audit (`scripts/audit.py`). `task.py add` accepts `--next` to allocate the next task id atomically. Review findings and deferred work are tracked as issues with stable IDs (I-NNN) and an explicit lifecycle (`open` -> `resolved` | `accepted` | `superseded`); gates read only open issues by default.

For multi-repository plans, `workspace.json` (via `./scripts/workspace.py {add|list}`) declares the repositories; the primary at path `.` hosts `.plan/`. Tasks target a repository with `task.py add --repository <name>` (default: primary), each task's baseline and commit are confined to its own repository, and project QA and the release audit verify every declared repository. Its absence means a single-repository project, unchanged from before.

Cross-repository prerequisites are tracked in `linked.json` via `./scripts/linked.py {add|list|set-released|validate}`: each handoff records the linked repository, the required commit, its release state, and any temporary override. Any temporary override requires a finalization task (`task.py add --finalizes L-NNN`); Gate 1 and project approval enforce this, and a finalization task cannot complete against an unreleased dependency.

State carries a `schema_version`. `./scripts/migrate.py` migrates a legacy `.plan/` forward idempotently without discarding tasks, gates, or reviews, and state from a newer Outfit fails safely. See `MIGRATION.md` for the upgrade procedure, schema-change reference, and how legacy review files and deferred issues are handled. `task.py add` requires `--commit-type` and accepts optional `--commit-scope`; these values can be changed with `task.py update` before the task is terminal. The scripts enforce structural constraints (id formats, required fields, dependency existence and acyclicity), Conventional Commit metadata, the task-status state machine, and phase transition guards. If a script does not yet exist, the lead must stop and tell the user.

## Git is required

The project lives in a git repo (created by `plan-init.py` if needed). `.plan/` is added to `.git/info/exclude`, ignored by dirty-tree checks, and rejected if it appears in the index. Outfit never creates or modifies `.gitignore`. Repositories without `HEAD` receive a `chore: establish project baseline` commit that excludes `.plan/`; existing repositories receive no initialization commit.

The lead is the only committer. Workers do not commit; project changes accumulate in the working tree until `task.py set-status <id> done` commits them as `<type>(<optional-scope>): <task-title>`. Failed commits are fatal and revert the task state change. Gate approvals only update local `.plan/` state and do not create commits.

Reviewers and QA workers see what changed via `git diff <baseline-sha>`, where the baseline is the project HEAD at dispatch time (recorded locally in `.plan/work/<task-id>/baseline-<role>.sha`).

## Files this skill manages

```
.plan/
├── plan.md              # lead-owned: high-level plan, milestones
├── stories/
│   └── S-001-<slug>.md  # lead-owned: user stories
├── tasks.json           # lead-owned: structured task state (managed by scripts/task.py)
├── status.json          # lead-owned: phase, milestone, gate status, schema_version
├── issues.json          # lead-owned: issue registry (managed by scripts/issue.py)
├── linked.json          # lead-owned: linked-project handoffs (managed by scripts/linked.py)
├── workspace.json       # lead-owned: multi-repo manifest (optional; managed by scripts/workspace.py)
├── decisions.md         # lead-owned: key decisions log (append-only)
├── codebase.md          # programmer-maintained: codebase map
└── work/
    ├── T-007-implement-login/   # task-level worker scratch (slug derived from title)
    │   ├── notes.md             # programmer scratch
    │   ├── rework-context.md    # combined reviewer+human feedback written by dispatch.py (on rework)
    │   ├── review-NN.md         # agent reviewer output, one immutable file per cycle
    │   ├── human-review-NN.md   # lead-recorded human review feedback, per cycle
    │   ├── review-response-NN.md # programmer's accepted/rejected per review issue, per cycle
    │   ├── status-programmer.md # done | blocked | needs-changes
    │   ├── status-reviewer.md
    │   ├── baseline-<role>.sha  # git HEAD at dispatch time, per role
    │   └── session-<role>-<ts>/ # pi session per dispatch (local only)
    │       ├── output.log       # raw worker output
    │       └── metadata.json    # role, model, baseline, timing, exit_code
    ├── M-001/                   # milestone-level QA scratch
    │   ├── qa.md                # qa output
    │   ├── status-qa.md
    │   ├── baseline-qa.sha      # recorded milestone-start baseline (set at set-milestone)
    │   └── session-qa-<ts>/     # local only
    └── project/                 # project-level QA scratch (dispatch.py qa project)
        ├── qa.md
        ├── status-qa.md
        └── baseline-qa.sha      # project-start (gate 1) baseline
```

The lead is the only writer of everything outside `work/`. Workers are the only writers inside `work/<their-task-id>/`.

## Entry point

Read `roles/lead.md` for the full lead instructions. Run `./scripts/detect-project.py`, confirm with the user if `greenfield`, then follow the matching bootstrap file: `bootstrap/greenfield.md`, `bootstrap/existing.md`, or `bootstrap/resume.md`.
