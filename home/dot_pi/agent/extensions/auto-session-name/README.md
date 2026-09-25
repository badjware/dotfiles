# auto-session-name extension

Names a session automatically from its first exchange and keeps the name current
as the conversation grows, so the session selector shows a readable title
instead of the raw first message.

## How it works

When the first agent run finishes (`agent_end`) with no name set, the extension
reads the first user message and first assistant reply, asks a model for a 3 to
6 word title, and sets it as the session display name.

After that, every 5 user turns it refreshes the title. Instead of resending the
whole conversation, it passes the model only the current title plus the latest
exchange, and asks it to keep the title if it still fits or refine it from the
new information. The turn count comes from the number of user messages on the
branch, so it survives `/reload` and `/resume`.

Refreshes always overwrite the current name, including one set via `/name`.

Naming is best-effort. If the model call or auth fails, the session keeps its
current name and nothing is reported.

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
