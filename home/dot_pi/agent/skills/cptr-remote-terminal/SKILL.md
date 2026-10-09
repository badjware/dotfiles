---
name: cptr-remote-terminal
description: "Run shell commands on a remote computer through an Open WebUI Computer (cptr) web terminal driven by the browser skill. Use when the user says a machine is \"accessible through cptr\", gives a cptr URL (e.g. http://HOST:PORT/?workspace=...), or asks to debug/inspect a remote PC via cptr in the browser."
---

## When to Use
The remote machine is only reachable through a cptr web UI. The cptr REST API needs cookie auth (POST /api/auth/login) and API keys only cover the /v1 gateway, so the browser terminal is the practical path. The user prefers interacting through the terminal; do not use eval.js fetch() calls to the cptr API to read files.

## Procedure
1. Load the browser skill (~/.pi/agent/skills/browser/SKILL.md) and run its scripts/setup.sh. If it fails (e.g. ERR_INVALID_AUTH_CREDENTIALS), stop and ask the user to fix it.
2. navigate.js straight to the workspace URL (http://HOST:PORT/?workspace=%2Fhome%2F<user>), then ax.js. Clicking workspace buttons on the cptr home page can time out even when they work. If a 'Sign In' form appears, ask the user to sign in themselves; never type their credentials.
3. Locate the terminal: ax.js shows a 'Terminal' tab and a textbox named 'Terminal input'. If no terminal tab exists, open one via 'New...' then the 'New Terminal' button (selector `role=button[name=/New Terminal/]`).
4. Before the first command, screenshot.js "main" once to check the terminal is at a shell prompt and not inside a pager (less), editor or running program. If it is in less, press q (key.js q) first.
5. Start a clean bash with no history and no user config: run.sh ' unset HISTFILE; HISTFILE= bash --norc --noprofile'. The leading space plus unset keeps the line out of the user's zsh history; HISTFILE= stops bash writing ~/.bash_history on exit; --norc --noprofile skips aliases (cat -> bat, ls -> lsd), the command-not-found handler and zsh's url-quote-magic, which inserts backslashes into lines typed after a URL. The prompt becomes `bash-5.3$`. Do this again in every new terminal tab. `exit` returns to the user's shell.
6. Run commands with scripts/run.sh (in this skill directory): `run.sh '<command>' [sleep_seconds=2] [tail_lines=40]`. It sends Control+u (clears the line, including escape-code junk like `10;rgb:d4d4/...` left in the input, and wakes xterm's input handling so fill() is not dropped), types the command, presses Enter, sleeps, then prints the tail of text.js "main". Pass an empty command (`run.sh '' 10 20`) to re-read the screen without typing.
7. Start commands with `clear;` so the screen only holds fresh output. The prompt no longer shows exit codes; append `; echo $?` when the status matters.
8. Keep each command's output short enough to fit on one screen: filter with rg, `| tail -N`, `sort | uniq -c`. Run several small commands instead of one huge dump.
9. The shell keeps state between commands. Instead of one long line, set variables in separate short commands (e.g. `T=$(curl ... | jq -r .token)`, then `U=https://...`, then `curl -H "Authorization: Bearer $T" $U`). Long typed lines get wrapped and are hard to verify on screen.
10. For long-running commands, poll with `run.sh '' <sleep>` until the prompt returns. Never type a new command while one is running; it becomes that program's input.
11. For read-only investigation, run commands freely. Ask the user before commands that change state (editing configs, restarting services); back up files before editing (cp f f.bak).

## Pitfalls
- Typing into a terminal that sits in `less` sends keystrokes as pager commands; 's' opens 'Log file' and can write junk files to the cwd. Always confirm a shell prompt first, and clean up any accidental file.
- Avoid backslashes in typed commands. They pass through local bash quoting and type.js before reaching the remote shell. Use single quotes for literals, character classes instead of escapes (e.g. rg '[[]wayland[]]'), and `; echo` instead of `\n` in format strings. Pass the whole command to run.sh in single quotes locally so $ reaches the remote shell untouched. For commands mixing single and double quotes, write the command locally with a quoted heredoc (cat > /tmp/cmd.txt <<'EOF' ... EOF) and pass it as run.sh "$(cat /tmp/cmd.txt)". Keep it on one line; newlines in fill() act as Enter. To write a remote file, use echo '...' > file, flattening content to one line when the format allows it.
- Check a tool exists with `command -v tool` before calling it. If the prompt does not come back, send key.js Control+c "role=textbox[name='Terminal input']".
- A terminal tab can stop accepting input (often after a page reload): keystrokes are not echoed and text.js returns stale content that does not match a screenshot. Do not keep retyping; open a fresh tab via 'New...' > 'New Terminal' and redo step 5 there.
- Avoid commands that open pagers or never exit (journalctl without --no-pager, systemctl status without --no-pager, tail -f, watch).
- When the same browser is used for another site (e.g. a router UI), navigate.js back to the cptr workspace URL before typing; the scripts act on the current page.
- cptr can leak file descriptors (inotify + pipes) and start failing with 'Too many open files'; check `ls /proc/<cptr pid>/fd | wc -l` vs `prlimit -n`. The fix is `systemctl --user restart cptr`, which kills the terminal session, so let the user run it.
- Do not use screenshots to read normal output; text.js on 'main' is enough. Screenshots are only for checking terminal state when text output is ambiguous.

## Verification
1. run.sh output shows the command's output followed by a fresh `bash-5.3$` prompt.
2. `run.sh 'clear; date; hostname'` returns the remote host's name, confirming you're on the right machine.
3. `run.sh 'clear; echo "hist=[$HISTFILE]"; type cat'` prints `hist=[]` and `cat is /usr/bin/cat`.
