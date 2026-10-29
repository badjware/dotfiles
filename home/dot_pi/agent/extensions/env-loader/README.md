# env-loader extension

Loads environment variables from every `~/.pi/agent/*.env` file (or
`$PI_CODING_AGENT_DIR/*.env`) and injects them into `process.env` at pi startup,
so any tool or script pi spawns (bash tool, skill scripts, etc.) inherits them.
Files are loaded in alphabetical order.

## Install

Already placed at `~/.pi/agent/extensions/env-loader.ts` (auto-discovered by pi).

## Config file format

The file follows the dot-env format: each line is `KEY=VALUE` with optional quoting, and `#` for comments.

## Precedence

By default, values in `*.env` files do **not** overwrite variables already set
in your shell. Set `PI_ENV_LOADER_OVERRIDE=1` to reverse this.

When several files define the same key, the first file alphabetically wins by
default. With `PI_ENV_LOADER_OVERRIDE=1` or `/env-loader`, the last one wins.
A warning is printed for each key defined in more than one file.

## Commands

- `/env-loader` rescans the directory, reloads every `*.env` file, and reports which var names were loaded vs.
  skipped (already set in the environment). Values are never printed.