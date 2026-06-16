# pi-claude-bridge

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that makes Claude Code assets automatically available inside pi.

## What it bridges

| Asset | Pi equivalent |
|---|---|
| `~/.claude/CLAUDE.md` | Injected eagerly into the system prompt |
| `CLAUDE.md` | Injected eagerly into the system prompt |
| `~/.claude/commands/**/*.md` | Prompt templates (`/command-name`) |
| `.claude/commands/**/*.md` | Prompt templates (`/command-name`) |
| `~/.claude/skills/` | Skill paths (auto-loaded) |
| `.claude/skills/` | Skill paths (auto-loaded) |
| `~/.claude/rules/**/*.md` | Injected into the system prompt (read-on-demand) |
| `.claude/rules/**/*.md` | Injected into the system prompt (read-on-demand) |

## What it does NOT bridge

- `settings.json` (hooks, allowedTools, deniedTools) — not merged or applied
- `CLAUDE.local.md` — not loaded (personal overrides; use pi's own config for that)

## Slash commands → Prompt templates

Any `.md` file under `.claude/commands/` or `~/.claude/commands/` is registered
as a pi prompt template. Claude Code and pi use the **same syntax** for
argument interpolation (`$ARGUMENTS`, `$1`, `$@`), so no conversion is needed.

Example — `.claude/commands/review.md`:
```markdown
Review the following code for bugs and style issues:

$ARGUMENTS
```

In pi this becomes available as `/review <code>`.

Subdirectory commands are supported: `.claude/commands/git/commit.md` registers
as `/commit` (using the filename, not the full path).

## Skills

Any directory at `.claude/skills/` or `~/.claude/skills/` is added to pi's
skill search paths. Skills are discovered and loaded automatically by pi.

## CLAUDE.md

`CLAUDE.md` at the project root and `~/.claude/CLAUDE.md` globally are read
eagerly and injected into the system prompt at the start of each agent turn,
matching how Claude Code treats them.

`~/.claude/CLAUDE.md` is skipped when `~/.pi/agent/AGENTS.md` exists, since
both serve the same purpose and the content is typically identical.

## Rules

`.md` files under `.claude/rules/` and `~/.claude/rules/` are **not** loaded
eagerly (they can be large). Instead, a list of the available rule files is
appended to the system prompt at the start of each agent turn, instructing the
model to `read` the relevant ones when needed.

## Status command

```
/claude-bridge
```

Prints a summary of all discovered commands, skills, and rules for the current
working directory.
