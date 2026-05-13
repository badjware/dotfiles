---
name: worldbuilding
description: Manages a structured knowledge base for fictional worlds used in storywriting (characters, locations, factions, items, events, lore, sessions). Each world lives in its own folder as Markdown files with YAML frontmatter, cross-linked by stable IDs, and indexed for fast retrieval. Use whenever the user wants to create/update/query worldbuilding entries, check canon consistency, look up relationships, resolve @id references, or list events on a timeline. This skill manages the knowledge base only — it does not write story prose.
compatibility: Requires python3 (stdlib only). Plain-text files; git-friendly.
---

# Worldbuilding

Structured, git-friendly knowledge base for fictional worlds. Each entry is a Markdown file with YAML frontmatter. Cross-links use stable IDs (e.g. `char-elira`). A deterministic `index.json` enables fast lookup without reading every file.

**Scope:** This skill manages the world's knowledge base (CRUD, queries, consistency checks, reference expansion). **It does not write narrative prose** — that belongs to a separate storywriting skill, which can consume this one's output.

## When to use

Trigger this skill whenever the user:
- Creates/updates/removes a worldbuilding entry
- Asks about a character, location, faction, item, event, lore topic, or session note
- Wants to find entries by tag, type, or relation
- Asks "who is connected to X?" / "what happens in chapter N?" / "is this consistent with canon?"
- Mentions `@some-id` references that should be expanded
- Wants to rebuild the index or initialize a new world

## Layout

Default location: `./worlds/<world-name>/` in the current working directory. A different parent can be passed with `--path`.

```
worlds/<world-name>/
  world.md              # premise, tone, high-level rules
  index.json            # auto-generated; committed for diffs
  characters/<id>.md
  locations/<id>.md
  factions/<id>.md
  items/<id>.md
  events/<id>.md        # datable/chapter-anchored
  lore/<id>.md          # magic, religion, cosmology, deities
  sessions/<id>.md      # chapter/session notes
  species/<id>.md       # races, creatures, bestiary
  cultures/<id>.md      # peoples, customs, languages
  documents/<id>.md     # in-world letters, books, prophecies, inscriptions
```

Every entry file is named `<id>.md`. IDs are stable, lowercase-kebab, prefixed by type (`char-`, `loc-`, `fac-`, `item-`, `evt-`, `lore-`, `sess-`, `spec-`, `cult-`, `doc-`).

## Entry format

```markdown
---
id: char-elira
type: character
name: Elira Vance
aliases: ["The Ashborn"]
tags: [protagonist, mage, northern-kingdom]
related: [loc-ravenhold, fac-silver-circle]
summary: Exiled battle-mage hunting the people who burned her village.
updated: 2026-05-12
# type-specific fields (e.g. for events: chapter, date)
---

# Elira Vance

Free-form prose: backstory, description, notes...
```

- `summary` (1–2 sentences) is what the agent loads from the index when it needs many entries cheaply.
- `related` uses IDs; the index builds a reverse-link graph.
- Frontmatter keys are written in stable order for clean git diffs.

See [references/schema.md](references/schema.md) for per-type fields.

## Usage

All operations go through one CLI. Run from the skill directory so relative paths resolve:

```bash
(cd <skill-dir> && python3 ./scripts/wb.py <command> [args])
```

### Commands

```bash
# Create a new world
wb.py init <world-name> [--path <parent-dir>]

# Create a new entry (prints the created file path; opens a template)
wb.py new <world-dir> --type <type> --name "<Display Name>" [--id <id>] [--tags a,b] [--related id1,id2] [--summary "..."]

# Read an entry
wb.py get <world-dir> <id>

# Query entries (prints JSON list of matching {id, type, name, summary, path})
wb.py find <world-dir> [--type T] [--tag T] [--related ID] [--q "text"]

# Graph neighbors of an entry (incoming + outgoing)
wb.py related <world-dir> <id>

# Timeline of events (sorted; optionally filtered)
wb.py timeline <world-dir> [--until-chapter N] [--until-date YYYY-MM-DD]

# Expand @id mentions in a block of text to "Name (id)"
wb.py expand <world-dir> --text "Elira met @loc-ravenhold..."

# Rebuild index.json (run after manual edits)
wb.py index <world-dir>

# Validate: broken references, duplicate IDs, missing required fields
wb.py check <world-dir>
```

`<world-dir>` can be an absolute path or a world name resolvable under `./worlds/`.

## Agent workflow rules

1. **Before creating an entry**, always run `wb.py find` to check for an existing one (avoid duplicates).
2. **Before asserting a fact** in conversation, consult `wb.py get` or `find` — do not invent canon. If the user states something new, offer to persist it.
3. **Consistency check**: when the user adds or changes a fact, run `wb.py check` afterwards and report any broken references.
4. **After any write** (new/update/delete), run `wb.py index <world-dir>` so the index stays current.
5. **Timeline awareness**: when the user asks "what does X know at chapter 7?", filter events with `wb.py timeline --until-chapter 7`.
6. **Expand references**: if the user writes `@some-id` in a message, call `wb.py expand` to resolve them before answering.
7. **Git**: entries and `index.json` are meant to be committed. After meaningful changes, suggest a commit; do not commit automatically.
8. **No prose writing**: if the user asks for story prose, reply that this skill only manages the world and suggest invoking a storywriting skill — but still gladly return structured world data it can consume.

## Updating entries

To update an entry, read the file, edit the frontmatter or body directly (standard `edit` tool), then run `wb.py index <world-dir>`. The script does not need to mediate edits — plain-text files are the source of truth.

## Referencing a world to an agent

A world can be "attached" to a conversation by telling the agent its path. The agent then uses that path as `<world-dir>` for every command in the session. Suggested phrasing to the user on first use:

> Tell me the world's path (e.g. `./worlds/mythia`) and I'll use it for the rest of this conversation.
