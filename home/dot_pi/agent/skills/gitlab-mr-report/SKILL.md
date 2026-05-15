---
name: gitlab-mr-report
description: Generates a Markdown report of all open GitLab merge requests the current user has authored or is a reviewer on, highlighting areas that need attention (discussion threads awaiting their reply, stale MRs with no activity in 7+ days, draft MRs, merge conflicts, failing pipelines) and summarizing the code areas touched. Use whenever the user asks for a status/summary/report of their GitLab MRs, their review backlog, or "what MRs need my attention".
compatibility: Requires python3 (stdlib only). Optional glab CLI for auth fallback. Network access to the target GitLab host.
---

# GitLab MR Report

Generates a Markdown report of open merge requests where the current user is the **author** or a **reviewer** on GitLab, flagging items that need attention.

## What gets flagged

- 🔴 **Awaiting your reply** — unresolved discussion threads on MRs you authored, or threads where you commented, when the last note is not from you
- 🟠 **Stale** — no activity in the last 7 days
- 🟡 **Draft** / WIP
- 🔀 **Merge conflicts**
- 🛑 **Failing pipeline**
- 📋 **Snapshot table** — per-MR overview: role, approvals (got/required), pipeline status, conflicts, draft, files changed, +/- lines, age. Approvals/pipeline reflect the author's POV even for MRs you're only reviewing.

MRs belonging to **archived projects** are filtered out before any of the
flags or the snapshot are computed. The report header notes how many were
hidden when this happens.

## Setup

Full configuration details are in [README.md](README.md) — point the user there on any
auth/setup error. Provide the user with a full path to the README.md, but do not read its content.

## Usage

Run the script from the skill directory and show its Markdown output to
the user. Invoke it with the skill directory as the working directory so
the relative path resolves regardless of where the skill is installed
(user-level skills dir, project-level skills dir, a plugin/package, or an
ad-hoc path supplied by the host agent):

```bash
(cd <skill-dir> && python3 ./scripts/mr_report.py)
```

This is the **only** supported invocation — do not call the script any
other way (no direct absolute paths, no re-implementation, no piping
through another wrapper).

If it fails with an auth error, tell the user to either:
- `export GITLAB_TOKEN=<personal-access-token>` (and `export GITLAB_HOST=<host>` for self-hosted), or
- run `glab auth login`

## Tuning

- `STALE_DAYS` at the top of `scripts/mr_report.py` controls the staleness threshold (default 7).
- `HTTP_TIMEOUT`, `PER_PAGE`, and `USER_AGENT` are also tunable module-level constants.

## Output

The script prints a Markdown report to stdout with two sections:

1. **Snapshot** — per-MR table (title, role, approvals, pipeline, conflicts, draft, files, +/-, age). A ✅ appended to the `Role` cell indicates that the *current user* has approved the MR; a 👍 indicates they gave a thumbs-up reaction without formally approving (shown regardless of whether they're formally tagged as a reviewer).
2. **🧩 Data (for Focus generation)** — a fenced JSON block with:
   - `stale_days` — the staleness threshold (mirrors the header).
   - `focus` — an object keyed by Focus category name (`merge_ready`,
     `review_queue`, `thumbs_upped`, `authored_conversations_waiting`,
     `reviewing_replies_waiting`, `commented_awaiting_response`,
     `needs_rebase`, `awaiting_approvals`, `candidates_to_close`).
     Each value is a pre-sorted list of `ref` strings (or, for
     `needs_rebase`, `{ref, reason}` objects where `reason` is
     `"conflicts"` or `"ready-needs-merging"`). **The script is the
     authoritative implementation of the inclusion rules — the LLM
     must not re-filter.**
   - `mrs` — an array of every MR with every `MRRow` field (`ref`, `url`,
     `roles`, `age_days`, `draft`, `conflict`, `pipeline`, `pipeline_bad`,
     `waiting`, `commented_awaiting`, `files`, `added`, `removed`,
     `approvals_got`, `approvals_required`, `approved_by_me`,
     `thumbs_upped_by_me`). Use this only to look up contextual fields for
     MRs already chosen by `focus`.

## Rendering the Focus section

You **must** then append a third section — `## 🎯 Focus` — plus an
optional **Suggestions** block. The full rendering rules, marker
conventions, category template, and Suggestions guidelines live in
[references/focus-template.md](references/focus-template.md).

**Read that file now before generating the Focus section.** It is the
authoritative spec for everything below the 🧩 Data block; do not
improvise. The Focus section carries all the "needs attention" signal
that used to live in a dedicated bucket list — don't reintroduce one.
