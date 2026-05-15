# worldbuilding

A pi skill that maintains a plain-text canon store for a fictional world. The storywriting skill reads from it to generate consistent prose; this skill never writes prose itself.

See [SKILL.md](SKILL.md) for the agent-facing spec.

## Quick start

```bash
WB=~/.pi/agent/skills/worldbuilding/scripts/wb.py

mkdir world
python3 "$WB" new --type character --name "Jane Doe" --tags "protagonist,detective" --summary "Burned-out detective."
python3 "$WB" new --type location  --name "Precinct 12" --summary "Run-down police precinct."

python3 "$WB" find --type character
python3 "$WB" related char-jane-doe
python3 "$WB" timeline --until-chapter 5
python3 "$WB" check
```

All commands accept `--world <dir>` to point at a non-default location.

## Requirements

Python 3 standard library only.
