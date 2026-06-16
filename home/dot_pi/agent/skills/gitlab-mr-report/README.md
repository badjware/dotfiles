# gitlab-mr-report

A skill that generates a Markdown report of all open GitLab merge requests
where the current user is the author or a reviewer, highlighting areas that
need attention.

See [`SKILL.md`](SKILL.md) for the skill manifest and agent-facing instructions.
This README covers **configuration**.

---

## Requirements

- `python3`
- A GitLab **Personal Access Token** (PAT), or a working `glab auth login` session

---

## Configuration

Auth and host are resolved in this order:

| Priority | Source                          | Purpose              |
| -------- | ------------------------------- | -------------------- |
| 1        | `GITLAB_TOKEN` env var          | API token            |
| 1        | `GITLAB_HOST` env var           | Hostname (no scheme) |
| 2        | `~/.config/glab-cli/config.yml` | Fallback for both    |

### Option A: Personal Access Token (recommended for portability)

```bash
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
# Optional:
export GITLAB_HOST="gitlab.example.com"
```

Put these in your shell profile (`~/.bashrc`, `~/.zshrc`, …) so the skill picks
them up automatically.

### Option B: Reuse `glab` credentials

If you already use the [`glab`](https://gitlab.com/gitlab-org/cli) CLI:

```bash
glab auth login
```

The skill will read the host and token from `~/.config/glab-cli/config.yml`.

---

## Required token permissions

| Scope      | Why                                                                  |
| ---------- | -------------------------------------------------------------------- |
| `read_api` | Read MRs, discussions, changes, and pipeline status via the REST API |

`read_api` is sufficient; the skill performs **no writes**. Do **not** grant
`api`, `write_repository`, or admin scopes unless you need them for other tools.

### What the skill calls

For reference/audit, the script hits only these read-only endpoints:

- `GET /user`
- `GET /merge_requests?scope=created_by_me&state=opened`
- `GET /merge_requests?scope=all&reviewer_username=<me>&state=opened`
- `GET /projects/:id/merge_requests/:iid` (detail, for `head_pipeline`, `has_conflicts`)
- `GET /projects/:id/merge_requests/:iid/pipelines` (fallback when detail has no pipeline)
- `GET /projects/:id/merge_requests/:iid/diffs` (paginated; falls back to `/changes` on older instances)
- `GET /projects/:id/merge_requests/:iid/approvals`
- `GET /projects/:id/merge_requests/:iid/discussions`
- `GET /projects/:id` (to detect archived projects; their MRs are hidden from the report)

---

## Tuning

Module-level constants at the top of `scripts/mr_report.py`:

- `STALE_DAYS` (default `7`): threshold for the "stale" flag.
- `HTTP_TIMEOUT` (default `30`): per-request timeout, in seconds.
- `PER_PAGE` (default `100`): GitLab API page size for paginated calls.
- `USER_AGENT` (default `gitlab-mr-report`): sent on every request.
