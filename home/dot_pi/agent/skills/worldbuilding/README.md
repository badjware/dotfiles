# worldbuilding

A pi skill for managing a structured, git-friendly knowledge base for fictional worlds used in storywriting.

Each world is a folder of Markdown files with YAML frontmatter, cross-linked by stable IDs. A deterministic `index.json` enables fast queries without reading every file.

This skill **does not write prose** — it only manages the world's knowledge base. Pair it with a separate storywriting skill that consumes its output.

See [SKILL.md](SKILL.md) for agent-facing instructions and [references/schema.md](references/schema.md) for the entry schema.

## Quick start (human)

```bash
SKILL=~/.pi/agent/skills/worldbuilding

# Create a world (default parent: ./worlds/)
(cd "$SKILL" && python3 ./scripts/wb.py init "Mythia")
# -> ./worlds/mythia/

W=./worlds/mythia

# Add entries
(cd "$SKILL" && python3 ./scripts/wb.py new "$W" --type character --name "Elira Vance" --tags "protagonist,mage" --summary "Exiled battle-mage.")
(cd "$SKILL" && python3 ./scripts/wb.py new "$W" --type location  --name "Ravenhold"   --summary "Fortress city in the north.")

# Query
(cd "$SKILL" && python3 ./scripts/wb.py find    "$W" --type character)
(cd "$SKILL" && python3 ./scripts/wb.py related "$W" char-elira-vance)
(cd "$SKILL" && python3 ./scripts/wb.py timeline "$W" --until-chapter 5)
(cd "$SKILL" && python3 ./scripts/wb.py expand  "$W" --text "Meet @char-elira-vance in @loc-ravenhold")

# After manual edits
(cd "$SKILL" && python3 ./scripts/wb.py index "$W")
(cd "$SKILL" && python3 ./scripts/wb.py check "$W")
```

## Git

Everything under a world dir is plain text and meant to be committed:
- One entry per file → clean per-entry diffs.
- Frontmatter keys written in a stable order → minimal noise.
- `index.json` is deterministic and committed; rebuild after edits.

## Requirements

Python 3 standard library only.
