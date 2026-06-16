# storywriting

A pi skill for managing a storywriting project: outlines, per-scene drafts, revisions, continuity checks, and manuscript compilation. Backed by an attached **worldbuilding** world (same on-disk format) which remains the single source of truth for canon.

This skill **does not call an LLM**. `draft` and `revise` return a deterministic JSON "prompt package"; the agent writes the prose.

See [SKILL.md](SKILL.md) for agent-facing instructions, [references/schema.md](references/schema.md) for frontmatter schemas, and [references/prompt-packages.md](references/prompt-packages.md) for the package shape.

## Quick start (human)

```bash
SW=~/.pi/agent/skills/storywriting

# One-time: create a story attached to a world
(cd "$SW" && python3 ./scripts/sw.py init "Cold Case" \
    --world ./world --pov char-jane-doe --tense past \
    --logline "A detective reopens the case that ended her partner's career.")

S=./stories/cold-case

# Outline
(cd "$SW" && python3 ./scripts/sw.py new-outline "$S" --scope arc)
(cd "$SW" && python3 ./scripts/sw.py new-outline "$S" --scope chapter --chapter 1)

# Scenes
(cd "$SW" && python3 ./scripts/sw.py new-scene "$S" \
    --chapter 1 --order 1 --pov char-jane-doe --where loc-precinct-12 \
    --summary "Jane reopens the file at @loc-precinct-12.")

# Let the agent draft it (returns a JSON package it will write against)
(cd "$SW" && python3 ./scripts/sw.py draft "$S" sc-ch01-s01)

# After agent writes prose into the scene file body:
(cd "$SW" && python3 ./scripts/sw.py set-status "$S" sc-ch01-s01 draft)
(cd "$SW" && python3 ./scripts/sw.py continuity "$S")
(cd "$SW" && python3 ./scripts/sw.py compile "$S")
(cd "$SW" && python3 ./scripts/sw.py status "$S")
```

## Capabilities

1. **Outlining**: arc + per-chapter beat files.
2. **Scene drafting**: prompt package with world context + style + adjacent scenes.
3. **Revision passes**: `revise --goal "..."` produces a package with the existing prose attached.
4. **Dialogue polishing**: use `revise` with a goal like `"polish @char-mark-lin's dialogue to sound clipped and tired"`.
5. **Continuity checking**: `continuity` validates every `@id` reference against the attached world.
6. **Manuscript compilation**: `compile` stitches scenes → `chapters/ch-NN.md` → `manuscript.md` (Markdown only).

## Git

Everything is plain text; scenes are one-file-per-scene for clean diffs. `chapters/*.md` and `manuscript.md` are **generated**: rebuild with `sw.py compile`, don't hand-edit. Commit freely.

## Requirements

Python 3 standard library only.
