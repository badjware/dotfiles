# outfit

A pi skill that runs structured software projects with a small multi-agent team: a single user-facing *lead* plus non-interactive *programmer*, *reviewer*, and *QA* workers. The lead drives discovery, planning, and execution phases with explicit human-approval gates; workers operate in fresh sessions and communicate only through files in `.plan/`.

## Requirements

- `pi`
- `git`
- `python3`

## Quick start

```sh
cd <your-project>
pi
> /skill:outfit
```

The lead detects whether the directory is greenfield, an existing project, or an in-progress outfit run. For existing and in-progress projects it proceeds directly; for greenfield it asks you to confirm before initializing a new git repo. It then walks you through:

1. **Discovery**: lead asks what you want and writes user stories to `.plan/stories/`.
2. **Planning**: lead decomposes stories into tasks, records technology decisions, flags items that need your input. Offers to stress-test the plan using the `grill-me` skill. **Gate 1**: you approve the plan before any code is written.
3. **Execution**: for each task, the lead dispatches a programmer, then conducts concurrent agent + human review. The agent reviewer runs automatically; you review the diff interactively with the lead. Both reviews must approve (or have only minor issues) for the task to proceed. On `needs-changes` from either review, the programmer is re-dispatched once with combined feedback and may reject issues it disagrees with. State transitions and commits are automatic. **Milestone QA**: at the end of every milestone, the lead dispatches a QA worker to verify cumulative changes against milestone acceptance criteria. **Gate 2+**: the lead presents a summary with QA findings, accumulated deferred issues, and any programmer rejections; you decide which to schedule as cleanup tasks.

You only ever talk to the lead. Workers run as separate non-interactive `pi` processes and write their findings to files; the lead reads them and decides what to do next.

## Configuration

### Per-role models

Each worker role can use a different model via environment variables. If unset, pi's default model is used.

```sh
export OUTFIT_MODEL_PROGRAMMER=anthropic/claude-sonnet-4
export OUTFIT_MODEL_REVIEWER=anthropic/claude-opus-4
export OUTFIT_MODEL_QA=openai/gpt-4o-mini
```

The selected model is recorded in each `worker.log` header.

## Git workflow

The project lives in a git repo. **Clean up your working tree before running outfit.**

The lead is the only committer. Commits happen automatically at three named events:

- Gate 1 approval: `outfit: plan approved (gate 1)`
- Each task done: `outfit: <task-id> <task-title>`
- Milestone approval: `outfit: milestone <M> approved`

Workers never commit. Code changes accumulate in the working tree until the lead commits the task atomically once review and QA pass. **Failed commits are fatal**: the lead surfaces the error and waits for you to untangle it (hooks rejecting changes, missing git identity, etc.).

Reviewers and QA workers see exactly what changed via `git diff <baseline-sha>`, where the baseline is the project's HEAD at dispatch time.

## File layout

Outfit creates and manages `.plan/` in the project:

```
.plan/
├── plan.md              # high-level plan, milestones
├── stories/
│   └── S-001-<slug>.md  # user stories
├── tasks.json           # structured task state (managed by scripts/task.py)
├── status.json          # phase, milestone, gate approvals
├── decisions.md         # append-only decisions log
├── codebase.md          # programmer-maintained codebase map (≤150 lines)
└── work/
    ├── T-007/                   # per-task worker scratch
    │   ├── notes.md             # programmer's notes
    │   ├── review.md            # agent reviewer's findings
    │   ├── human-review.md      # human review feedback (recorded by lead)
    │   ├── review-response.md   # programmer's accepted/rejected per issue (on rework)
    │   ├── deferred-issues.md   # minor issues logged but not blocking
    │   ├── status-programmer.md # done | blocked | needs-changes
    │   ├── status-reviewer.md
    │   ├── baseline-<role>.sha  # git HEAD at dispatch
    │   ├── worker.log           # full transcript (gitignored)
    │   └── session-*/           # pi sessions per dispatch (gitignored)
    └── M1/                      # per-milestone QA scratch
        ├── qa.md                # QA's results
        ├── status-qa.md
        ├── baseline-qa.sha
        ├── worker.log           # gitignored
        └── session-*/           # gitignored
```

Worker logs and session directories are excluded by an outfit-managed block in `.gitignore`. The curated artifacts (`notes.md`, `review.md`, `qa.md`, status files, baselines) are committed and serve as the project's audit trail.

## Observing what the workers are doing

The lead is silent about the worker's transcripts on purpose (otherwise its context would bloat). To watch a worker live:

```sh
tail -f .plan/work/<task-id>/worker.log
```

To inspect a past dispatch:

```sh
ls .plan/work/<task-id>/session-*/
pi --resume <session-path>
```

## Resuming after interruption

If pi or your terminal dies mid-task, restart pi in the same directory and ask the lead to resume. It will inspect `status-<role>.md` files in `.plan/work/<task-id>/` for any task in a non-terminal state and either advance it or re-dispatch the relevant worker. See `roles/lead.md` "Resuming after interruption" for the procedure.

If the working tree is dirty when you resume, that means a previous task was mid-flight; let the lead finish or cancel it before starting anything else.

## Limitations

- One lead, one worker at a time: dispatches are synchronous. No parallel tasks.
- No mid-run worker intervention: once a worker is dispatched, the lead waits for it to finish or time out.
- Single-project orientation: outfit assumes one `.plan/` per project. Sub-projects in a monorepo are not modeled.
- Worker behavior is governed by the role markdown files in `roles/`. If you find a role drifting from the spec (lead skipping rework, reviewer being too lenient on acceptance, etc.), tighten the wording rather than adding code.

## Layout of this skill

```
outfit/
├── README.md          # this file
├── SKILL.md           # agent-facing description loaded by pi
├── roles/
│   ├── lead.md
│   ├── programmer.md
│   ├── reviewer.md
│   └── qa.md
├── bootstrap/
│   ├── greenfield.md
│   └── existing.md
├── templates/
│   ├── plan.md
│   └── story.md
└── scripts/
    ├── _state.py          # shared helpers
    ├── plan-init.py       # initialize .plan/ and git
    ├── detect-project.py  # greenfield/existing/in-progress
    ├── task.py            # task CRUD with state machine
    ├── status.py          # phase, milestone, gate approvals
    └── dispatch.py        # spawn a worker
```

The scripts are stdlib-only Python and the markdown files are static. There is no build step.
