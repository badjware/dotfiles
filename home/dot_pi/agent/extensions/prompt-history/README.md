# prompt-history extension

A [pi](https://github.com/mariozechner/pi-coding-agent) extension that adds persistent prompt history to the interactive editor:

- Every prompt you submit is saved to disk.
- `Ctrl+R` opens a fuzzy-search overlay over the full history.

## Storage

History lives at:

```
<pi-agent-dir>/prompt-history.jsonl
```

where `<pi-agent-dir>` is `$PI_CODING_AGENT_DIR` if set, otherwise `~/.pi/agent`. Each line is a JSON object `{ "text": "...", "timestamp": <ms> }`.

Behaviour:
- Loaded at startup and re-read before each `Ctrl+R` invocation.
- Only prompts submitted from interactive input are recorded (programmatic/scripted input is ignored).
- Empty/whitespace-only prompts are ignored.
- Duplicate prompts are deduplicated: if you re-submit an existing prompt, the older copy is removed and the new one becomes the most recent.
- Capped at **2000 entries**; oldest entries are dropped when the cap is exceeded. The file is rewritten only when dedup or trimming actually changes the set, otherwise entries are appended in place.
- Write failures are non-fatal (in-memory state is preserved; the next submission retries).

## `Ctrl+R`: fuzzy search overlay

Opens a bottom-anchored overlay containing:
- a live fuzzy-filter input,
- up to ~25 visible matches, newest at the bottom (closest to the input),
- selection wraps top↔bottom; a `(N/total)` indicator appears when older entries are scrolled off the top.

Pressing `Enter` inserts the selected entry into the editor. Pressing `Esc` cancels.
