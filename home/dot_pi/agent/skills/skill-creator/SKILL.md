---
name: "skill-creator"
description: "Guide for creating or updating a Pi agent skill. Use when the user wants to build a new skill or improve an existing one that packages specialized knowledge, workflows, scripts, or tool integrations for Pi."
version: 1
created: "2026-09-01"
updated: "2026-09-01"
---
## When to Use
Use when a request involves creating a new Pi skill or updating an existing one. Signals include "make a skill", "turn this workflow into a skill", "add a skill for X", or wanting to package repeated procedures, domain knowledge, or tool integrations so Pi can load them on demand. Skip only for one-off tasks with no reuse value.

## Procedure
1. Understand the use case first. Collect concrete example prompts that should trigger the skill and the outcomes expected. Ask the user for real trigger phrases; do not invent scope. Stop asking once the functionality is clear.
2. Plan reusable contents by walking each example: identify scripts/ for deterministic repeated code, references/ for detailed docs loaded on demand, and assets/ for files used in the skill's output. Include only what is actually needed; most skills need none of these.
3. Create the skill directory directly at a Pi discovery path, normally ~/.pi/agent/skills/<skill-name>/ for global skills or .pi/skills/<skill-name>/ for project skills. Pi discovers unpacked skills; there is no init or packaging step.
4. Write SKILL.md with valid YAML frontmatter: a lowercase-hyphenated name of 1-64 chars and a specific, non-empty description that states what the skill does and when to use it. Pi does not require the name to match the directory, though matching is clearer.
5. Write the body focused and lean (<5k words). Keep core procedure and workflow in SKILL.md; move schemas, long references, and examples into references/ files linked with relative paths. Do not duplicate content between SKILL.md and references.
6. Build any planned scripts, references, and assets, and delete unused scaffolding. Reference every bundled file from SKILL.md with a relative path so Pi knows how to use it.
7. Test in Pi: restart or refresh so discovery picks up the skill, confirm it appears in the available-skills list, then invoke it via /skill:<name> or a matching prompt. Iterate on wording and resources after real use.

## Pitfalls
- Pi loads unpacked skills straight from its discovery directories; do not scaffold or zip. Zipping is only useful for sharing a skill with someone else.
- A missing or empty description, or malformed frontmatter, prevents the skill from loading. Most other rule violations only warn.
- Name must be lowercase letters, numbers, and single hyphens, with no leading/trailing or consecutive hyphens, 1-64 chars.
- Name collisions across discovery locations keep the first found and warn; pick a unique name.
- Keep SKILL.md lean. Overstuffing it wastes context on every load; push detail into references/ loaded on demand.
- Write instructions for another Pi instance to follow: imperative, verb-first, objective language, not chatty second person.

## Verification
1. SKILL.md has valid YAML frontmatter with a lowercase-hyphenated name (1-64 chars) and a specific non-empty description.
2. The skill file sits under a Pi discovery path (e.g. ~/.pi/agent/skills/<name>/SKILL.md).
3. After refreshing discovery, the skill appears in Pi's available-skills list and loads without warnings.
4. Invoking /skill:<name> or a matching prompt loads the body and any referenced scripts/references/assets resolve via their relative paths.
5. Running the skill on a real example produces the intended outcome.