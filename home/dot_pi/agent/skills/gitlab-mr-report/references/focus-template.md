# Focus Section: Rendering Rules & Template

Load this file after running the script. It specifies how to render the
final `## 🎯 Focus` section from the 🧩 Data JSON block the script emits.

## Rendering rules (important)

- Present the script's Snapshot section to the user **verbatim**: it
  already contains a clickable `[ref](url)` link for every MR.
- The 🧩 Data section is machine-readable scaffolding. **Do not render it
  to the user.** Parse it internally to drive Focus, then drop it.
- **Build every Focus category by iterating the corresponding
  `focus.<category>` list in the order the script emits it.** Look up each
  `ref` in `mrs` only to fetch the contextual fields you're going to
  display. You must not re-filter, re-sort, or second-guess the script's
  membership: if an MR is absent from `focus.review_queue`, it does not
  belong there, full stop.
- **Always** emit the Focus section at the end. Never skip it, even if every
  category is empty (use `_(none)_` for empties).
- **Every MR you mention anywhere**: in the verbatim sections, in Focus,
  or in any ad-hoc commentary, must be a Markdown link (`[ref](url)`).
  Never collapse to a bare code span like `` `!123` ``.
- When grouping or repeating an MR across sections, repeat the full link
  each time rather than linking only on first mention.
- Do not invent new Focus categories. If the data suggests one, surface
  that as a suggestion *after* the Focus section.

## Focus rules

- Every MR reference is a Markdown link: `[ref](web_url)`: look up `url`
  in `mrs` by `ref`.
- An MR may appear in multiple categories (e.g. stale + needs rebase).
  **Repetition is expected; do not dedupe across categories.** The
  script already places an MR in every category it qualifies for.
- Preserve the script's ordering within each category. Do not re-sort.
- Category headings and their order are **fixed**: do not rename, reorder,
  merge, or add categories. Propose additions after the section instead.
- Empty categories (`focus.<name>` is `[]`): keep the heading, write
  `_(none)_` as the sole body line. Never drop a category.
- Per MR: link + short context + the fields that justify placement and
  the sort keys (typically 2–3 of `approvals`, `+N/-M`, `files`, `age`,
  thread count). Don't dump every column, but don't under-context either.
- `STALE_DAYS` is printed in the report header and in the JSON as
  `stale_days`; use that value for any stale decoration below.
- **Marker placement is always leading, never inline.** Any marker emoji
  (⭐, 🟠, and any future ones) goes in a dedicated slot *before* the
  `[ref](url)` link, separated from it by a single space. Do not
  re-emit the same marker later in the bullet's prose. In particular,
  🟠 for `age_days >= stale_days` applies to **every** Focus category
  that lists an MR where age is relevant (Review queue, Thumbed up,
  Conversations waiting on you, Commented awaiting response, Awaiting
  approvals, Candidates to close), not just Review queue. If multiple markers
  apply, concatenate them in that same leading slot with no space
  between them (e.g. `⭐🟠`). The age value itself may still appear in
  the trailing context fields as plain text (e.g. `81d old`), but
  without the emoji.

## Focus template

Each subsection below names the `focus.<category>` key it renders from
and any inline decorations to apply. **Inclusion rules are documented in
the script (`build_focus()` in `scripts/mr_report.py`) and are not
re-evaluated here.**

### 🟢 Merge-ready (yours)
Source: `focus.merge_ready`. Include approvals and pipeline status.

### 👀 Review queue (waiting on you)
Source: `focus.review_queue`. In addition to the global 🟠-stale rule,
prefix the first 1–2 entries with ⭐ (the script has already sorted by
quickest wins: fewest files, then smallest total diff). ⭐ is unique
to this category. The script excludes MRs where your latest unresolved
comment is awaiting a response (those appear under **Commented: awaiting
response**) and MRs where you have given a 👍 (those appear under
**Thumbed up**).

Start the rendered subsection with a one-line legend so the meaning of
the markers is obvious at a glance:

> _⭐ = quickest win (fewest files, smallest diff) · 🟠 = stale (no activity in ≥ `stale_days`)_

### 👍 Thumbed up (read, not yet approved)
Source: `focus.thumbs_upped`. MRs where you are a reviewer, have given a
👍 emoji reaction (signalling you read it but chose not to formally approve
because you don’t own the project), and have not formally approved. Include
role, files, +/- diff, and age. These are separated from the Review queue
so they don’t create noise, but should still be checked occasionally in
case the MR has been updated since you thumbed it up.

### 💬 Conversations waiting on you
Merge `focus.authored_conversations_waiting` and
`focus.reviewing_replies_waiting` into a single list. Deduplicate by
`ref` (an MR in both lists appears once). Preserve the script's
ordering: authored entries first (in their original order), then
reviewing-only entries (in their original order). Include `waiting` as
the thread count, the role(s) from `mrs[].roles` (e.g. `author`,
`reviewer`, `author/reviewer`), and flag any with `conflict == true`.

### 💬 Commented: awaiting response
Source: `focus.commented_awaiting_response`. Include role and
`commented_awaiting` as the thread count. (Applies regardless of role,
author or reviewer.)

**Direction:** in every MR in this category, **you** wrote the last note
and are waiting for the **other party** to respond or resolve. The
primary action is to follow up with or ping the author/reviewer. Never
describe these as threads where someone is waiting on you.

### 🛠 Needs rebase (yours)
Source: `focus.needs_rebase` (each entry is `{ref, reason}`). Render
`reason == "conflicts"` as **conflicts** and
`reason == "ready-needs-merging"` as **"ready, needs merging"**.

### 📣 Awaiting approvals (yours)
Source: `focus.awaiting_approvals`. Include approvals (got/required)
and age.

### 🗑 Candidates to close
Source: `focus.candidates_to_close`. Authored MRs only. Just the link +
age. Triage candidates, not reviews.

## 💡 Suggestions (free-form, after Focus)

After the Focus section, append a short **Suggestions** block,
separated from Focus by a `---` horizontal rule, calling out 1–3 MRs
that stand out as the user's highest-leverage next actions. This is the
one place where you are allowed (and expected) to exercise judgment
beyond the script's precomputed buckets. It is advisory prose, **not** a
new Focus category; never rename, reorder, or add to the fixed Focus
categories above.

Rules:

- **Zero to three bullets**, no more. Omit the whole block (including
  the `---` rule and heading) if nothing is genuinely worth surfacing.
  Don't pad it.
- Each bullet is free-form prose, but must still reference MRs as
  Markdown links (`[ref](url)`), same as everywhere else.
- Lead with the **heading line** `**Suggestions:**` so the section is
  visually distinct from Focus and obviously advisory.
- Draw on signals the fixed Focus categories don't combine well, e.g.:
  - An MR that is simultaneously **stale + draft + has waiting threads**
    ("push to completion or close?").
  - The **oldest** entry in `commented_awaiting_response` with a high
    thread count (likely the highest-leverage followup; remember: you
    are waiting on the other party here; the suggested action is to ping
    them, not to reply yourself).
  - A **large** MR (high `files` or `+N/-M`) that's also stale,
    conflicted, or has a failing pipeline (🛑), where rebasing/fixing will
    only get harder.
  - An MR flagged in **several** Focus categories at once: repetition
    across buckets is a real signal worth naming explicitly.
- Do **not** just restate a single Focus bullet. Each suggestion should
  add a recommendation or combine signals the reader would otherwise
  have to synthesize themselves.
- Never invent a new named category here; keep it prose bullets. If a
  pattern recurs run-over-run, raise it with the user instead of
  codifying it silently.
