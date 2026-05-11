# env-loader extension

Loads environment variables from `~/.pi/agent/config.env` and injects them into
`process.env` at pi startup, so any tool or script pi spawns (bash tool, skill
scripts, etc.) inherits them — without touching your shell rc files.

## Install

Already placed at `~/.pi/agent/extensions/env-loader.ts` (auto-discovered by pi).

## Config file format

Create `~/.pi/agent/config.env` (dotenv-style):

```sh
# Comments are allowed
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_HOST=gitlab.example.com

# Quotes are optional but respected
SOME_VAR="value with spaces"

# Leading `export` is tolerated
export ANOTHER_VAR=foo
```

Then lock it down (recommended, since tokens live here):

```bash
chmod 600 ~/.pi/agent/config.env
```

The extension prints a warning if the file is group/other-readable.

## Precedence

By default, values in `config.env` do **not** overwrite variables already set
in your shell. Set `PI_ENV_LOADER_OVERRIDE=1` to reverse this.

## Commands

- `/env-loader` — lists the names (not values) of vars loaded from the file.

## Behavior

- Missing file → silent no-op.
- Malformed lines → skipped with a warning on stderr.
- Invalid key names (not `[A-Za-z_][A-Za-z0-9_]*`) → skipped with a warning.
