# Story Schema

All story artifacts are Markdown files with YAML frontmatter. Frontmatter is written in a stable key order for clean git diffs.

## `story.md`

Top-level project file. One per story.

```yaml
---
id: story
type: story
title: Cold Case
world: ../../world           # path to a worldbuilding world (relative to story dir)
pov_default: char-jane-doe
pov_mode: limited-third      # first | limited-third | omniscient
tense: past                  # past | present
logline: "A detective reopens the case that ended her partner's career."
tags: [crime, contemporary]
updated: 2026-05-12
---
```

Body: premise, themes, anything freeform. The `draft` package pulls `title`, `logline`, `pov_mode`, and `tense` from here.

## Outline files

One per scope. `outline/arc.md` covers the whole story; `outline/ch-NN.md` covers a chapter.

```yaml
---
id: out-arc           # or out-ch01
type: outline
scope: arc            # arc | chapter
chapter: 1            # only when scope == chapter
summary: "Act I: Jane is pulled back onto the case."
updated: 2026-05-12
---
```

Body: free-form beats. Conventions (not enforced):
- Use `-` bullets for beats.
- Reference world IDs as `@char-jane-doe`, `@loc-precinct-12`.
- Mark open questions with `TODO:`.

## Scene files

One per scene, under `scenes/<id>.md`. ID format: `sc-chNN-sMM` (e.g. `sc-ch01-s03`).

```yaml
---
id: sc-ch01-s01
type: scene
chapter: 1
order: 1
pov: char-jane-doe
where: loc-precinct-12
characters: [char-jane-doe]
status: outline          # outline | draft | revised | final
summary: Jane reopens the file at Precinct 12.
word_count: 0
pov_mode_override: null  # optional: override story pov_mode for this scene
tense_override: null     # optional: override story tense for this scene
updated: 2026-05-12
---

# sc-ch01-s01

(Prose goes here. Initially empty; filled in by the drafting agent.)
```

### Field notes
- `pov`, `where`, and entries in `characters` must be IDs that exist in the attached world. `sw.py continuity` validates this.
- `status` transitions are advisory: `outline → draft → revised → final`.
- `word_count` is refreshed by `sw.py index`; do not set by hand.

## Notes files

Plain Markdown, no frontmatter required:
- `notes/continuity.md`: running continuity notes the agent or user maintains by hand.
- `notes/todo.md`: open threads, unresolved promises, invented names that need worldbuilding entries.

## Compiled artifacts (generated: do not edit)

- `chapters/ch-NN.md`: scenes of chapter N concatenated in `order`, frontmatter stripped, separated by blank lines.
- `manuscript.md`: all chapters concatenated in order.

Both are rebuilt by `sw.py compile`. Hand edits will be overwritten.

## ID prefixes

| Artifact | Prefix |
|----------|--------|
| scene    | `sc-`  |
| outline  | `out-` |

Scene IDs also encode chapter/order for readability: `sc-ch01-s03`. The `chapter` and `order` fields remain the source of truth.
