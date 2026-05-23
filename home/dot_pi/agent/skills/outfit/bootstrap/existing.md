# Bootstrap: existing

Use when the user wants to add a feature (or a related set of features) to an existing project.

## Steps

1. **Survey the project.** Quick read: top-level files, README, `AGENTS.md` / `CLAUDE.md` if present, package manifest, primary source layout. Goal: enough to ask informed discovery questions, not a full audit. Do not write findings anywhere yet; this is for your own context.

2. **Check for prior `.plan/`.** If `.plan/` already exists from a previous outfit run:
   - If the previous run is complete (all tasks `done`, all gates approved), archive it: rename to `.plan.archive-<date>/` and proceed with a fresh init.
   - If it is mid-flight, stop and ask the user whether to resume (continue from current `status.json` via `scripts/status.py show`) or archive and restart.

3. **Initialize `.plan/`** with `scripts/plan-init.py` if not resuming.

4. **Capture project context once, in `decisions.md`.** Append a "Project context" section noting: language(s), framework(s), test runner, lint/format tools, branching conventions if obvious. This is the constraint set workers will respect. Keep it short; link to existing docs rather than restating them.

5. **Do not refactor or "tidy up" anything.** Existing-project bootstrap is read-only on the codebase.

6. **Enter discovery phase.** Run `scripts/status.py set-phase discovery`, declare `[phase: discovery]`, and ask the user about the feature: what it is, who it is for, how it fits with the existing product, what is explicitly out of scope, what existing behavior must not change.

## Notes

- Discovery for an existing project tends to surface "but the current code does X, so we need Y" pseudo-requirements. Keep stories at the user-value level; implementation constraints belong in `decisions.md` or in task descriptions during planning.
- If the feature requires touching a part of the codebase you have not surveyed, note it as a planning-phase task ("survey module X") rather than doing it now.
