# auto-session-name extension

Names a session automatically from its first exchange, so the session selector
shows a readable title instead of the raw first message.

## How it works

When the first agent run finishes (`agent_end`), the extension reads the first
user message and first assistant reply, asks a model for a 3 to 6 word title,
and sets it as the session display name. It runs only when no name is set yet,
so a manual `/name` or an already-named session is left alone.

Naming is best-effort. If the model call or auth fails, the session keeps its
default name and nothing is reported.

## Install

Placed at `~/.pi/agent/extensions/auto-session-name/` (auto-discovered by pi).

## Model

By default the current session model generates the title. Override it with
`PI_SESSION_NAME_MODEL` in `provider/model` format:

```
PI_SESSION_NAME_MODEL=google/gemini-2.5-flash
```

If the override is malformed or the model has no configured auth, no name is
set.
