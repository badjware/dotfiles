---
name: gitlab-mr-review
description: "Deep-reviews a GitLab merge request: semantic what/why/how analysis, flags code areas needing attention (correctness risks, design choices, security implications, missing tests, introduced TODOs), lists existing discussion threads to avoid duplicates, answers questions about the MR, and proofreads the user's draft review notes for grammar and correctness. Use when the user wants to review a GitLab MR or asks about a specific MR."
---

# GitLab MR Review

Assists with reviewing a GitLab merge request in three phases: initial analysis, Q&A, and notes proofreading.

## Setup

If auth fails, tell the user to set:
- `export GITLAB_TOKEN=<personal-access-token>`
- `export GITLAB_HOST=<host>` (only needed for self-hosted instances)

## Phase 1: Fetch and analyze

If the user provided an MR URL (as a command argument or in their message), use it. Otherwise ask for it.

Run the fetch script:

```bash
python3 ./scripts/fetch_mr.py <mr-url>
```

The script outputs JSON with two keys:
- `mr`: metadata (title, description, branches, draft, pipeline, conflicts, reviewers)
- `changes`: list of file diffs (`old_path`, `new_path`, `diff`, flags)

If `skipped_binary_files` is present, mention it briefly.

### Analysis to produce

**Do not** report things the user can see for themselves (author, pipeline status, conflict status, file sizes). Focus on understanding.

Read [references/overview-template.md](references/overview-template.md) and fill it in. Follow it exactly: omit sections that do not apply, do not add sections that are not in the template.

---

## Phase 2: Q&A

Answer questions about the MR. Reference specific files, functions, or diff lines when relevant.

If something the user asks about cannot be answered from the current context (e.g. after a compaction), re-run the fetch script to restore the data, then answer.

---

## Phase 3: Notes proofreading

When the user asks to review their draft notes, fetch them from the GitLab API:

```bash
python3 ./scripts/fetch_draft_notes.py <mr-url>
```

If no draft notes are found, tell the user.

The script also returns `discussions` (existing comment threads). Check each draft note against them and call out any that duplicate or closely overlap an existing thread so the user can decide whether to post it.

Review the notes on two dimensions:

1. **Grammar and clarity**: fix typos, awkward phrasing, unclear references. Suggest reworded versions where helpful.

2. **Correctness**: verify every factual claim against the diff:
   - Does the code actually do what the user says it does?
   - Is the user's suggested fix or advice technically sound given the full context of the changes?
   - Are there any contradictions with other parts of the diff the user may have missed?

Present the proofread version with issues called out inline, then a clean final version the user can copy-paste.
