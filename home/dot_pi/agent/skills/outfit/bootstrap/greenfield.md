# Bootstrap: greenfield

Use when `./scripts/detect-project.py` reports `kind: greenfield`, or the user has confirmed greenfield after a different detection result.

## Detection

Run `./scripts/detect-project.py`. If the result is `greenfield`, **confirm with the user before proceeding**: this is the point of no return for `git init`. If the user says this is actually an existing project, switch to `bootstrap/existing.md`.

## Steps

1. **Initialize `.plan/` and git.** Run `./scripts/plan-init.py`. This will:
   - run `git init` if cwd is not already a git repo
   - create `.plan/` (refuses if it already exists)
   - add a `.gitignore` block excluding `.plan/work/*/session-*/`
   - make an initial commit `outfit: initialize .plan/`

   If the script does not exist, stop and tell the user.

2. **Do not pick a tech stack yet.** Stack is a planning-phase decision, recorded in `decisions.md`. Discovery phase is about what and why, not how.

3. **Do not scaffold the project structure.** Scaffolding (running `npm init`, creating directory layouts, etc.) is a programmer-worker job during execution, driven by tasks the lead writes during planning. The first milestone will typically include a "scaffold project" task.

4. **Enter discovery phase.** Status starts at `discovery` from `plan-init.py`; declare `[phase: discovery]` and begin asking the user about the project: what it is, who it is for, what success looks like, what is explicitly out of scope. Use `templates/story.md` for stories.

## Notes

- The first story is often a high-level "elevator pitch" story. Refine and split it into smaller stories as the user clarifies.
- Resist the urge to ask 20 questions at once. Three or four per turn.
