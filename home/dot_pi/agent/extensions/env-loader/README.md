# env-loader extension

Loads environment variables from `~/.pi/agent/config.env` and injects them into
`process.env` at pi startup, so any tool or script pi spawns (bash tool, skill
scripts, etc.) inherits them.

## Install

Already placed at `~/.pi/agent/extensions/env-loader.ts` (auto-discovered by pi).

## Config file format

The file follows the dot-env format: each line is `KEY=VALUE` with optional quoting, and `#` for comments.

## Precedence

By default, values in `config.env` do **not** overwrite variables already set
in your shell. Set `PI_ENV_LOADER_OVERRIDE=1` to reverse this.

## Commands

- `/env-loader` reloads the file and reports which var names were loaded vs.
  skipped (already set in the environment). Values are never printed.