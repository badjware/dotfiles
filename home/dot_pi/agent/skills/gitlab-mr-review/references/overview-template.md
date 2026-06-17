# MR Review: {title}

`{source_branch}` → `{target_branch}`

---

## What

{2-4 sentence summary of what the MR does, based on description and diffs.}

## Why

{Motivation behind the change. Flag if unclear.}

## How

{Approach taken: architecture, patterns, notable implementation choices. Reference specific files/functions.}

---

## Areas Needing Attention

> Omit any category that does not apply.

### Correctness Risks
{Logic that looks wrong or fragile, unhandled edge cases, error handling gaps.}

### Design Concerns
{Questionable abstractions, coupling, duplication, deviation from codebase conventions.}

### Introduced Complexity
{Abstractions that may not pull their weight, new patterns diverging from conventions, hard-to-follow logic, new dependencies.}

### Security / Auth
{Changes to auth flows, secrets handling, input validation, privilege escalation paths.}

### Missing Tests
{Changed logic with no accompanying test changes.}

### Introduced TODOs / FIXMEs
{New TODOs or FIXMEs added in this MR.}

### Sensitive Paths
{Config files, infrastructure, deployment scripts, secret management.}
