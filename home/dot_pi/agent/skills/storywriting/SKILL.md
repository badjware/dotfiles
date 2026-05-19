---
name: storywriting
description: Manages a storywriting project (outlines, scenes, chapters, revisions, manuscript compilation) and writes prose on demand, backed by an attached worldbuilding knowledge base. Each story lives in its own folder with per-scene Markdown files so drafts and revisions are git-friendly and easy to parse. Use whenever the user wants to outline a story, draft or revise a scene, check continuity against the world, compile chapters/manuscript, or get a project status report. Pairs with the `worldbuilding` skill, which remains the source of truth for canon.
compatibility: Requires python3 (stdlib only). Plain-text files; git-friendly. Optionally reads a worldbuilding world folder (same on-disk format as the `worldbuilding` skill).
---

# Storywriting

Structured, git-friendly storywriting project. Outline → scene specs → scene drafts → compiled chapters → manuscript. Each scene is a Markdown file with YAML frontmatter so the agent can load, edit, and revise it in isolation.

**Scope:** This skill owns story artifacts (outlines, scenes, chapters, manuscript, style). It **does not define world canon** — characters, locations, factions, lore all live in a world managed by the `worldbuilding` skill. This skill reads the world for context but never edits it.

## When to use

Trigger this skill whenever the user:
- Starts a new story or attaches an existing one
- Writes, revises, or polishes a scene / chapter / dialogue pass
- Wants a scene drafted in a specific POV's voice
- Wants a continuity check between a draft and world canon
- Compiles chapters or the full manuscript
- Asks for project status (word counts, scene statuses, open threads)
- References a character/location by `@id` while writing

## Layout

Default location: `./stories/<story-name>/` in the current working directory. Override parent with `--path`.

```
stories/<story-name>/
  story.md              # frontmatter: world path, POV, tense, logline; body: premise/themes
  STYLE.md              # voice, tone, vocabulary, pacing rules
  outline/
    arc.md              # full-story beats
    ch01.md             # per-chapter beats
  scenes/
    sc-ch01-s01.md      # one file per scene (frontmatter + prose)
  chapters/
    ch01.md             # compiled artifact (regenerated from scenes/)
  manuscript.md         # compiled full book (regenerated)
  notes/
    continuity.md       # running notes
    todo.md             # open threads, per-scene TODOs
  index.json            # generated; committed for diffs
```

Chapters and manuscript are **compiled artifacts** — regenerate, do not hand-edit.

## Relationship to the worldbuilding skill

- `story.md` frontmatter has `world: <path>` pointing at a worldbuilding world folder (relative paths resolved against the story dir).
- Before drafting, this skill reads the relevant world entries directly from disk (same Markdown-with-frontmatter format).
- This skill **never writes** to the world folder. If prose invents new named entities, report them so the user can hand them to the `worldbuilding` skill.

## Entry formats

See [references/schema.md](references/schema.md) for full frontmatter schemas (story, outline, scene).

### Scene frontmatter (core)
```yaml
id: sc-ch01-s01
type: scene
chapter: 1
order: 1
pov: char-jane-doe           # world ID
where: loc-precinct-12       # world ID
characters: [char-jane-doe]
status: outline|draft|revised|final
summary: Jane reopens the file at Precinct 12.
word_count: 0
updated: 2026-05-12
```

## Drafting model

`draft` and `revise` do **not** call an LLM. They assemble a deterministic **prompt package** (JSON) the agent uses to write the prose itself. See [references/prompt-packages.md](references/prompt-packages.md).

A prompt package includes:
- story metadata (POV mode, tense, logline)
- `STYLE.md` contents
- arc outline + relevant chapter outline
- target scene spec (summary, POV, where, characters)
- adjacent scene summaries (previous + next) for continuity
- world context: full entries for POV, location, and named characters; short summaries for any other `@id` referenced
- warnings (e.g. missing chapter outline, unresolved `@id`)
- writing instructions (POV, tense, style reminders)

After writing, the agent saves prose into the scene file body and updates `status` and `word_count` via `sw.py set-status` / `sw.py index`.

## Usage

All operations go through one CLI. Run from the skill directory:

```bash
(cd <skill-dir> && python3 ./scripts/sw.py <command> [args])
```

### Commands

```bash
# Create a new story
sw.py init <name> [--path <parent>] [--world <world-path>] [--pov <id>] [--tense past|present] [--logline "..."]

# Outlines
sw.py new-outline <story> --scope arc
sw.py new-outline <story> --scope chapter --chapter N

# Scenes
sw.py new-scene <story> --chapter N --order K --pov <id> [--where <id>] [--characters a,b] [--summary "..."]
sw.py set-status <story> <scene-id> <outline|draft|revised|final>

# Write / revise (returns JSON prompt package — agent writes the prose)
sw.py draft   <story> <scene-id>
sw.py revise  <story> <scene-id> --goal "tighten pacing"

# Continuity: scan scene prose for @id mentions, validate against the world
sw.py continuity <story> [--chapter N]

# Compile scenes → chapters → manuscript (Markdown only, v1)
sw.py compile <story> [--chapter N]

# Status report (JSON): word counts, scene statuses, warnings
sw.py status <story>

# Rebuild index.json (run after manual edits)
sw.py index <story>

# Resolve @id mentions in text → "Name (@id)"
sw.py expand <story> --text "Meet @char-jane-doe at @loc-precinct-12"
```

`<story>` can be an absolute path or a name resolvable under `./stories/`.

## Agent workflow rules

1. **Attach on first use**: if no story path has been named, ask the user for one (or offer `sw.py init`).
2. **Outline-before-draft (soft)**: `draft` warns if no chapter outline exists but still produces a package. Surface the warning to the user and offer to create an outline first.
3. **Always load the prompt package**: do not write prose from memory. Call `sw.py draft` (or `revise`) and write strictly against the returned package.
4. **POV discipline**: the package specifies POV character, POV mode, and tense — obey them. If the user asks to break them for a single scene, overwrite that scene's frontmatter (`pov`, `pov_mode_override`) first.
5. **Canon respect**: if the prompt package's `warnings` includes broken `@id` references or missing world, stop and confirm with the user before inventing facts. Invented names go into `notes/todo.md`, then optionally to the worldbuilding skill.
6. **Save prose into the scene file body**, keep frontmatter intact, then run `sw.py index` to refresh word counts and index.
7. **Continuity pass**: after drafting, run `sw.py continuity` and surface any broken or unknown `@id`s.
8. **Compile is write-only on artifacts**: never edit `chapters/*.md` or `manuscript.md` by hand — regenerate with `sw.py compile`.
9. **Git**: suggest commits at meaningful milestones (outline done, scene drafted, chapter compiled); never commit automatically.
10. **Hand-off, don't overreach**: if a scene introduces new named entities (a character, a place, a faction), list them in the response and suggest invoking the `worldbuilding` skill to persist them. Do not edit the world from this skill.

## Style guide

`STYLE.md` is one file per story. Keep it short and concrete: POV mode, tense, vocabulary preferences (what to avoid, what to favor), pacing rules, dialogue conventions. The draft/revise packages inject it verbatim.

## Updating

Edit any file with the standard `edit` tool; run `sw.py index` afterwards to refresh the index and word counts. Scene files are the source of truth.
