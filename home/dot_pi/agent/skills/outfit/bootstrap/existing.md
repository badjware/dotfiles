# Bootstrap: existing

Use when `./scripts/detect-project.py` reports `kind: existing`.

## Detection

Run `./scripts/detect-project.py`. If the result is `existing`, proceed. If the result is `in-progress`, use `bootstrap/resume.md` instead. If the result is unexpectedly `greenfield`, confirm with the user before switching to `bootstrap/greenfield.md`.

## Steps

1. **Survey the project.** Quick read: top-level files, `README.md`, package manifest, primary source layout, presence of a test suite. (`AGENTS.md` and `CLAUDE.md` are loaded automatically by pi; you do not need to read them.) Goal: enough to ask informed discovery questions, not a full audit. Do not write findings anywhere yet; this is for your own context.

2. **Initialize `.plan/` and git.** Run `./scripts/plan-init.py`. The script will:
   - refuse if the working tree is dirty
   - create `.plan/` and the `.gitignore` block
   - make an initial commit `outfit: initialize .plan/`

   If `plan-init.py` refuses because the tree is dirty, **stop and surface the message to the user**. The user is responsible for cleaning the tree (commit, stash, reset, restore, whatever they prefer). **Do not commit, stash, reset, or otherwise touch the user's pre-existing changes** on their behalf.

3. **Capture project context once, in `decisions.md`.** Append a "Project context" section noting: language(s), framework(s), test runner, lint/format tools, branching conventions if obvious. This is the constraint set workers will respect. Keep it short; link to existing docs rather than restating them.

4. **Do not refactor or "tidy up" anything.** Existing-project bootstrap is read-only on the codebase.

5. **Enter discovery phase.** Declare `[phase: discovery]` and ask the user about the feature: what it is, who it is for, how it fits with the existing product, what is explicitly out of scope, what existing behavior must not change.

## Notes

- Discovery for an existing project tends to surface "but the current code does X, so we need Y" pseudo-requirements. Keep stories at the user-value level; implementation constraints belong in `decisions.md` or in task descriptions during planning.
- If the feature requires touching a part of the codebase you have not surveyed, note it as a planning-phase task ("survey module X") rather than doing it now.
