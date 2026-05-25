# Bootstrap: greenfield

Use when `scripts/detect-project.py` reports `kind: greenfield`, or the user has confirmed greenfield after a different detection result.

## Detection

Run `scripts/detect-project.py`. It reports one of `greenfield`, `existing`, or `in-progress`, with the signals that drove the decision. **Always state the detection result to the user and ask them to confirm** before following a bootstrap file. If the user disagrees, follow the bootstrap they ask for.

## Steps

1. **Initialize `.plan/` and git.** Run `scripts/plan-init.py`. This will:
   - run `git init` if cwd is not already a git repo
   - create `.plan/` (refuses if it already exists)
   - add a `.gitignore` block excluding `.plan/work/*/worker.log` and `.plan/work/*/session-*/`
   - make an initial commit `outfit: initialize .plan/`

   If the script does not exist, stop and tell the user.

2. **Do not pick a tech stack yet.** Stack is a planning-phase decision, recorded in `decisions.md`. Discovery phase is about what and why, not how.

3. **Do not scaffold the project structure.** Scaffolding (running `npm init`, creating directory layouts, etc.) is a programmer-worker job during execution, driven by tasks the lead writes during planning. The first milestone will typically include a "scaffold project" task.

4. **Enter discovery phase.** Status starts at `discovery` from `plan-init.py`; declare `[phase: discovery]` and begin asking the user about the project: what it is, who it is for, what success looks like, what is explicitly out of scope. Use `templates/story.md` for stories.

## Notes

- The first story is often a high-level "elevator pitch" story. Refine and split it into smaller stories as the user clarifies.
- Resist the urge to ask 20 questions at once. Three or four per turn.
