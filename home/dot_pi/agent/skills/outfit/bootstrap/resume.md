# Bootstrap: resume

Use when `./scripts/detect-project.py` reports `kind: in-progress` (i.e. `.plan/` already exists).

## Detection

Run `./scripts/detect-project.py`. For `in-progress`, proceed with this bootstrap path. If result is `greenfield` or `existing`, use the corresponding bootstrap file.

## Steps

1. **Read the current state.**
   ```bash
   ./scripts/status.py show
   ./scripts/task.py list --include-cancelled
   ```

2. **Determine if the run is complete.**
   - All tasks are `done` or `cancelled`
   - All defined milestone gates are approved (check `milestone_gates` in status output)
   - If `gate_1_approved: true`, the planning phase was completed
   
   If complete, ask the user whether to:
   - Archive the old plan (`mv .plan .plan.archive-$(date +%Y%m%d)`) and start a new greenfield/existing bootstrap for a new feature
   - Treat this as a continuation (adding new stories/milestones on top of the completed work)

3. **If mid-flight, resume the interrupted run.**
   - Read `.plan/decisions.md` for project context
   - Read stories in `.plan/stories/` to understand the feature scope
   - Check current phase from `./scripts/status.py show`
   - **Do NOT run `./scripts/plan-init.py`** (plan is already initialized)

4. **Determine current state and next action.**
   
   **If phase is `discovery`:**
   - Continue discovery conversation with user
   - Once stories are confirmed by the user, run `./scripts/status.py approve-discovery` to commit stories + decisions.md and advance to planning atomically (Gate 0)
   
   **If phase is `planning`:**
   - Check if tasks exist (`./scripts/task.py list`)
   - If no tasks yet, complete the planning phase
   - Once tasks are defined for all stories, use `./scripts/status.py approve-gate-1` to commit and advance to execution
   
   **If phase is `execution`:**
   - Identify the current task:
     - If `current_milestone` is set, filter to that milestone
     - Look for tasks with status `in_progress` or `in_review` first
     - Otherwise, find the next `todo` task whose dependencies are all `done`
   - Resume work on that task or select the next task to start

5. **Declare the phase and next action to the user.**
   Example: `[phase: execution, milestone: M-002, resuming task T-007 (in_review)]`

## Notes

- The `.plan/work/<task-id>/` directory contains the full audit trail for each task (code, reviews, test results, session logs)
- If the working tree is dirty (uncommitted changes outside `.plan/`), alert the user. The previous run may have been interrupted mid-task
- Check `.plan/work/<task-id>/status-*.md` files to see what the programmer/reviewer/QA last reported
- Check git log for `outfit:` commits to see the progression history
