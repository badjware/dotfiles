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
3. **Execution**: for each task, the lead dispatches a programmer, then conducts concurrent agent + human review. The agent reviewer runs automatically; you review the diff interactively with the lead. Both reviews must approve (or have only minor issues) for the task to proceed. On a blocker or major finding from either review, the programmer is re-dispatched with combined feedback (immutable, cycle-numbered review files) and may reject issues it disagrees with; findings are tracked in the issue registry with stable IDs. Local state transitions are automatic, and completed tasks create Conventional Commits for project changes. **Milestone QA**: at the end of every milestone, the lead dispatches a QA worker to verify cumulative changes against the recorded milestone-start baseline. **Gate 2+**: the lead presents a summary with QA findings and the open issue registry; you decide which to schedule as cleanup tasks. **Project completion**: after the final milestone, whole-project QA plus an automatic release audit (`approve-project`) distinguish feature-complete from release-ready.

You only ever talk to the lead. Workers run as separate non-interactive `pi` processes and write their findings to files; the lead reads them and decides what to do next.

## Configuration

### Per-role models

Each worker role can use a different model via environment variables. If unset, pi's default model is used.

```sh
export OUTFIT_MODEL_PROGRAMMER=anthropic/claude-sonnet-4
export OUTFIT_MODEL_REVIEWER=anthropic/claude-opus-4
export OUTFIT_MODEL_QA=openai/gpt-4o-mini
```

The selected model is recorded in each `session-<role>-<ts>/metadata.json`.

## Git workflow

The project lives in a git repo. **Clean up project changes before running outfit.** Changes inside `.plan/` are ignored by Outfit's dirty-tree checks.

`.plan/` is local orchestration state. Outfit adds it to `.git/info/exclude`, explicitly verifies that it is not staged, and never creates or modifies project `.gitignore` files. If `.plan/` is already tracked from an older run, Outfit stops rather than rewriting history.

The lead is the only committer. Workers never commit. Code changes accumulate in the working tree until a reviewed task becomes done. Each task records a required Conventional Commit type and an optional scope, producing messages such as:

```text
feat: add session renewal
fix(auth): handle expired sessions
docs(api): document authentication errors
```

Common types include `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `build`, `ci`, `perf`, `style`, and `revert`. Repository-specific instructions take precedence.

Discovery, planning, and milestone approvals update local state without creating empty commits. A repository without `HEAD` receives `chore: establish project baseline`, excluding `.plan/`; an existing repository receives no initialization commit. **Failed task commits are fatal**: the task status is reverted and the lead waits for you to resolve the error.

Reviewers see project changes via `git diff <baseline-sha>` (the repository HEAD at dispatch time). QA workers diff against the recorded scope-start baseline: the milestone-start commit for milestone QA, and the gate-1 commit for project QA.

## File layout

Outfit creates and manages `.plan/` in the project:

```
.plan/
├── plan.md              # high-level plan, milestones
├── stories/
│   └── S-001-<slug>.md  # user stories
├── tasks.json           # structured task state (managed by ./scripts/task.py)
├── status.json          # phase, milestone, gate approvals, schema_version
├── issues.json          # issue registry (managed by ./scripts/issue.py)
├── linked.json          # linked-project handoffs (managed by ./scripts/linked.py)
├── workspace.json       # multi-repo manifest, optional (managed by ./scripts/workspace.py)
├── decisions.md         # append-only decisions log
├── codebase.md          # programmer-maintained codebase map
└── work/
    ├── T-007-implement-login/   # per-task worker scratch (slug from title)
    │   ├── notes.md             # programmer's notes
    │   ├── rework-context.md    # combined feedback for rework (written by dispatch.py)
    │   ├── review-NN.md         # agent reviewer's findings, one immutable file per cycle
    │   ├── human-review-NN.md   # human review feedback per cycle (recorded by lead)
    │   ├── review-response-NN.md # programmer's accepted/rejected per issue, per cycle
    │   ├── user-edit-NN.patch   # captured direct user edits during review (task.py user-edited)
    │   ├── status-programmer.md # done | blocked | needs-changes
    │   ├── status-reviewer.md
    │   ├── baseline-<role>.sha  # git HEAD at dispatch
    │   └── session-<role>-<ts>/ # pi session per dispatch (local only)
    │       ├── output.log       # raw worker output
    │       └── metadata.json    # role, model, baseline, timing, exit_code
    ├── project/                 # project-level QA scratch (dispatch.py qa project)
    │   ├── qa.md
    │   ├── status-qa.md
    │   └── baseline-qa.sha      # project-start (gate 1) baseline
    └── M-001/                   # per-milestone QA scratch
        ├── qa.md                # QA's results
        ├── status-qa.md
        ├── baseline-qa.sha
        └── session-qa-<ts>/     # local only
```

All `.plan/` content remains local, including session directories and curated artifacts such as notes, reviews, QA results, status files, baselines, and rework context.

## Observing what the workers are doing

The lead is silent about the worker's transcripts on purpose (otherwise its context would bloat). To inspect a past dispatch:

```sh
# find the session directory (slug-based task dir)
task_dir=$(python3 ./scripts/task.py work-dir <task-id>)
ls $task_dir/session-*/

# view output
cat $task_dir/session-<role>-<ts>/output.log

# view dispatch metadata
cat $task_dir/session-<role>-<ts>/metadata.json

# resume session in pi
pi --resume $task_dir/session-<role>-<ts>/<session-file>.jsonl
```

## Resuming after interruption

If pi or your terminal dies mid-task, restart pi in the same directory and ask the lead to resume. It will inspect `status-<role>.md` files in `.plan/work/<task-id>/` for any task in a non-terminal state and either advance it or re-dispatch the relevant worker. See `roles/lead.md` "Resuming after interruption" for the procedure.

If project files outside `.plan/` are dirty when you resume, a previous task may be mid-flight; let the lead finish or cancel it before starting anything else.

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
│   ├── existing.md
│   └── resume.md
├── templates/
│   ├── plan.md
│   └── story.md
└── scripts/
    ├── _state.py          # shared helpers
    ├── plan-init.py       # initialize .plan/ and git
    ├── detect-project.py  # greenfield/existing/in-progress
    ├── task.py            # task CRUD with state machine (+ amend, user-edited, review-state)
    ├── status.py          # phase, milestone, gate approvals, approve-project
    ├── issue.py           # issue registry (findings, deferred work)
    ├── linked.py          # linked-project handoffs
    ├── workspace.py       # multi-repository workspace manifest
    ├── audit.py           # release audit (run by approve-project)
    ├── migrate.py         # forward, idempotent schema migration
    └── dispatch.py        # spawn a worker
```

See `MIGRATION.md` for upgrading an existing `.plan/` and the schema-change reference.

The scripts are stdlib-only Python and the markdown files are static. There is no build step.
