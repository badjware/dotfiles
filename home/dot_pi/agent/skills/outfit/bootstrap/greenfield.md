# Bootstrap: greenfield

Use when the user is starting a new project from scratch in the current directory.

## Steps

1. **Confirm cwd is empty or near-empty.** If files exist that suggest an existing project (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `.git/` with history), stop and ask the user to confirm; you may be in the wrong directory or this should use `bootstrap/existing.md` instead.

2. **Initialize `.plan/`.** Run `scripts/plan-init.py` (if it does not exist yet, stop and tell the user). This creates:
   ```
   .plan/
   ├── plan.md             # from templates/plan.md, mostly empty
   ├── stories/            # empty
   ├── tasks.json          # {"tasks": []}
   ├── status.json         # {"phase": "discovery", "current_milestone": null, "gate_1_approved": false, "milestone_gates": {}}
   ├── decisions.md        # empty header
   └── work/               # empty
   ```

3. **Do not pick a tech stack yet.** Stack is a planning-phase decision, recorded in `decisions.md`. Discovery phase is about what and why, not how.

4. **Do not initialize git, package managers, or scaffolding.** Those are tasks the programmer worker will do during execution, driven by tasks the lead writes during planning. The first milestone will typically include a "scaffold project" task.

5. **Enter discovery phase.** Run `scripts/status.py set-phase discovery`, declare `[phase: discovery]`, and begin asking the user about the project: what it is, who it is for, what success looks like, what is explicitly out of scope. Use `templates/story.md` for stories.

## Notes

- The first story is often a high-level "elevator pitch" story. Refine and split it into smaller stories as the user clarifies.
- Resist the urge to ask 20 questions at once. Three or four per turn.
