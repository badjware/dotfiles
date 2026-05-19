---
name: worldbuilding
description: Plain-text canon store for a single fictional world used to ground prose generation. Entries are Markdown files with minimal YAML frontmatter (id, type, name, tags, related, summary), located under `./world/`, indexed in `index.json`. Use whenever the user wants to look up canon (characters, locations, events, lore, anything), add or update entries when iteration changes canon, or list events on a timeline. This skill manages the knowledge base only and does not write prose; pair it with a storywriting skill.
compatibility: Requires python3 (stdlib only). Plain-text files; git-friendly.
---

# Worldbuilding

## Purpose

A canon store the storywriting agent reads from to generate consistent prose, and writes to when iteration changes canon. The world lives under `./world/`, one Markdown file per entry. `world/index.json` is the cheap-context payload the agent loads first.

This skill does not write prose. It manages the data only.

## When to use

- The user asks anything about an entity in the world (character, place, faction, event, item, lore, custom).
- The user introduces a new fact, contradiction, or change while drafting; persist it.
- The user mentions an `@some-id` reference that should be resolved.
- About to draft prose: load `index.json`, identify relevant entries, read those files in full.

## Layout

```
world/
  world.md            # premise, tone, narrative voice (recommended)
  index.json          # generated; commit it
  characters/<id>.md  # convention; any subfolder works
  locations/<id>.md
  events/<id>.md
  ...
```

The index globs `world/**/*.md`. Folder structure is a human convention, not enforced.

## Entry format

```markdown
---
id: char-jane-doe
type: character
name: Jane Doe
tags: [protagonist, detective]
related: [loc-precinct-12, char-mark-lin]
summary: Burned-out detective investigating the case that ended her partner's career.
---

# Jane Doe

Free-form prose: backstory, voice, mannerisms, physical description, secrets,
and anything the agent should know when writing scenes with her.
```

### Required fields

- `id` (stable, lowercase-kebab, never renamed)
- `type` (free-form string; convention: `character`, `location`, `faction`, `item`, `event`, `lore`, `species`, `culture`, `document`, or whatever fits)
- `name`
- `summary` (1-2 sentences; this is what the agent loads in bulk)

### Optional fields

- `tags` (list of strings)
- `related` (list of IDs; the index builds a reverse-link graph)
- `chapter` (int) and `date` (string) on `type: event` entries; consumed by `timeline`

Anything else in the frontmatter is preserved but not interpreted. Prefer putting rich detail in the body.

### Frontmatter syntax

Strict subset of YAML, one `key: value` per line:
- strings (plain or `"quoted"`), integers, `null`/`~`
- flow lists: `tags: [a, b, "c with comma,"]`

No booleans, no maps, no block style. If you need structured data, write prose in the body.

## Commands

Default world is `./world/`; override with `--world <dir>`.

```bash
wb.py new --type T --name "<Name>" [--id ID] [--dir DIR] [--tags a,b] [--related id1,id2] [--summary "..."]
wb.py get <id>
wb.py find [--type T] [--tag T] [--related ID] [--q "text"]
wb.py related <id>
wb.py timeline [--until-chapter N] [--until-date YYYY-MM-DD]
wb.py index
wb.py check
```

`new` writes to `world/<type>s/<id>.md` by default and rebuilds the index. ID defaults to `<prefix>-<slug-of-name>` using a small built-in prefix table for the conventional types (see DEFAULTS in `wb.py`); pass `--id` to override.

## Agent workflow

### Reading canon (before writing prose)

1. Read `world/index.json` once. It contains every entry's id, type, name, tags, related, summary, plus reverse links. This is the cheap-context payload.
2. Identify ids relevant to the upcoming scene (by tag, by `related` neighborhood, by name match).
3. Read those entry files in full with `wb.py get` or by direct file read for depth.
4. For chapter-anchored stories, run `wb.py timeline --until-chapter N` to see only what has happened by chapter N.
5. Never invent canon facts. If a needed detail is missing, ask the user.

### Writing canon (during iteration)

1. When the user introduces a new fact, persist it: `wb.py new` for new entities, or edit the file directly for updates.
2. After any write, run `wb.py index` so the index is current.
3. Run `wb.py check` after meaningful changes; report any broken references or duplicates.
4. When draft prose introduces something not in canon (a side character, a place name), ask the user whether to canonize it. Don't silently expand the world.
5. Suggest a git commit after coherent batches of changes; do not commit automatically.

### Resolving references

When the user writes `@some-id` in a message, resolve it via `wb.py get` (or by globbing `world/**/<id>.md`) before answering. `wb.py` itself has no `expand` command; the agent does this inline. (The companion `storywriting` skill exposes its own `sw.py expand` for bulk-expanding mentions inside scene text.)

## Bootstrapping a world

There is no `init` command. To start a new world:

```bash
mkdir world
cat > world/world.md <<'EOF'
---
id: world
type: lore
name: <World Name>
summary: One-line premise.
---

# <World Name>

Premise, tone, narrative voice, anything that shapes prose generation.
EOF
python3 wb.py index
```

Then add entries with `wb.py new`.
