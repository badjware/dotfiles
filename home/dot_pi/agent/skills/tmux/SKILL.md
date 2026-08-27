---
name: tmux
description: "Control one tmux pane at a time for interactive terminal programs. By default creates one detached session; only select an existing pane when the user explicitly requests it."
compatibility: Requires tmux and ripgrep (rg) on PATH.
---

# tmux Skill

Controls exactly one tmux pane through scripts in `scripts/`. It uses the default tmux server and never creates a private socket. Never run raw `tmux` commands. Never chain skill scripts with `&&` or `;` in one `bash` call.

## Setup

Run once before controlling a new pane:

```bash
./scripts/setup.sh
```

`setup.sh` checks that tmux is available, creates a detached session with one pane, and records that pane as the only pane this skill may control. It is idempotent while that pane remains available.

If the script exits non-zero, stop and report the error. Do not create a tmux session manually.

After setup, tell the user how to monitor the controlled pane:

```bash
tmux attach -t <session>
```

Use `status.sh` to print the exact target and monitor command.

## Selecting an existing pane

Only use an existing pane when the user explicitly asks for it. First inspect the available panes:

```bash
./scripts/list.sh
```

Then select exactly one target:

```bash
./scripts/attach.sh session:window.pane
```

`attach.sh` does not attach a terminal client. It records that existing pane as the one pane the skill can control and replaces any previous selection. If the previous pane no longer exists, clear that stale selection. Changing selection must never kill a tmux session or pane.

## Input and output

All actions apply only to the recorded pane. Scripts do not accept pane targets.

```bash
./scripts/send.sh "python3 -q"     # literal text, pause before Enter and after execution
./scripts/send.sh -n "print('hi')" # literal text without Enter
./scripts/send.sh --stdin <<'PY'    # literal multi-line input, then Enter
print('hi')
PY
./scripts/send.sh -n --stdin <<'PY' # literal multi-line input without Enter
print('hi')
PY
./scripts/key.sh C-c                # control or named key
./scripts/capture.sh                # recent pane output (optional line count, default 200)
./scripts/wait.sh '^>>>' 15          # regex and optional timeout in seconds
./scripts/status.sh                 # target and monitor command
```

`send.sh` waits one second before Enter and one second after it. Use `capture.sh` to inspect output before sending further input. `wait.sh` polls the pane output and exits non-zero on timeout. Do not send an additional Enter after `send.sh` unless the captured pane state shows it is needed.

Never use the `write` tool to create a script for later invocation in the controlled pane. Send scripts directly to the pane with `send.sh --stdin`, such as a shell or Python heredoc, so all script creation and execution remains visible in the pane.

## Cleanup

Keep the session open by default. Only run cleanup when the user explicitly asks to close or stop the session. Otherwise leave the pane running so the user can keep monitoring it.

```bash
./scripts/cleanup.sh
```

Cleanup clears the recorded pane. If the skill created its detached session, it kills only that session. If the user selected an existing pane, cleanup never kills it. It never kills the tmux server or any unrelated session. Use it only when the user explicitly asks to close or stop the session, or to forget the current selection.
