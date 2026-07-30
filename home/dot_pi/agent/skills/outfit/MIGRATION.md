# Migrating an existing Outfit project

Outfit stamps `.plan/status.json` with a `schema_version`. Newer Outfit
releases add metadata; migration is forward-only, idempotent, and never deletes
tasks, gates, reviews, or any work artifact. You can upgrade an in-progress
`.plan/` without restarting the project.

## Upgrade procedure

1. Update the Outfit skill to the new version.
2. From the project root, preview the changes: `./scripts/migrate.py --dry-run`.
3. Apply them: `./scripts/migrate.py`. Re-running makes no further changes.
4. Resume normally (`bootstrap/resume.md`).

State written by a **newer** Outfit than the one you are running fails safely:
every script refuses rather than corrupting state. Upgrade Outfit; do not
downgrade state.

## Schema-change reference

| Version | Adds |
|---------|------|
| 1 | Original layout (no `schema_version`); legacy projects are treated as v1. |
| 2 | Explicit `schema_version` stamp; issue registry `issues.json`. |
| 3 | Linked-project handoff registry `linked.json`. |

`workspace.json` is optional at any version: its absence means a
single-repository project, which behaves exactly as before.

Baselines added by later releases:
- `status.json` `milestone_baselines[M-XXX]`: recorded when a milestone is
  activated, so QA always diffs from the milestone start.
- `status.json` `project_baseline`: recorded at Gate 1 for project QA.

Legacy projects migrated mid-flight do not have historical milestone baselines.
The next `status.py set-milestone` records the current milestone's baseline;
already-completed milestones cannot be retro-fitted and are simply not
re-QA'd.

## Legacy review files

Older projects wrote a single `review.md`, `human-review.md`, and
`review-response.md` per task. These remain readable after migration; they are
never rewritten. New review cycles use immutable, cycle-numbered files
(`review-01.md`, `human-review-01.md`, `review-response-01.md`, ...). When
resuming an older task mid-review, treat the un-numbered files as cycle 0 and
let the next reviewer dispatch write `review-01.md`.

## Classifying existing deferred issues

Older projects logged minor issues in per-task `deferred-issues.md` files.
Migration leaves those files in place (they are historical artifacts). To bring
them under the authoritative registry, add each one explicitly:

```
./scripts/issue.py add --source-task T-007 --severity minor-defect \
  --category tests --description "thin coverage on retry path" --location foo.py:42
```

Use the finding taxonomy when classifying: `blocker`, `major`, `minor-defect`,
`optional-enhancement`, `observation`. Only `blocker` and `major` force rework;
minor defects live in the registry until a cleanup task resolves them; optional
enhancements never block a gate.

## Rollback limitations

Migration is forward-only. There is no automated downgrade. If you must return
to an older Outfit, restore the pre-migration `.plan/` from your own backup;
the scripts will not rewrite `schema_version` downward or drop the registries
they added. Because `.plan/` is excluded from git (never committed), take a
filesystem copy before upgrading if you want a rollback point.
