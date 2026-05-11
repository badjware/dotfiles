# gitlab-mr-report

A skill that generates a Markdown report of all open GitLab merge requests
where the current user is the author or a reviewer, highlighting areas that
need attention.

See [`SKILL.md`](SKILL.md) for the skill manifest and agent-facing instructions.
This README covers **configuration** and **token permissions**.

---

## Requirements

- `python3` (standard library only — no `pip install` needed)
- A GitLab **Personal Access Token** (PAT), or a working `glab auth login` session

---

## Configuration

Auth and host are resolved in this order:

| Priority | Source                                   | Purpose               |
| -------- | ---------------------------------------- | --------------------- |
| 1        | `GITLAB_TOKEN` env var                   | API token             |
| 1        | `GITLAB_HOST` env var                    | Hostname (no scheme)  |
| 2        | `~/.config/glab-cli/config.yml`          | Fallback for both     |
| 3        | Default host `gitlab.com`                | Used if nothing else  |

### Option A — Personal Access Token (recommended for portability)

```bash
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
# Only needed for self-hosted GitLab:
export GITLAB_HOST="gitlab.example.com"
```

Put these in your shell profile (`~/.bashrc`, `~/.zshrc`, …) so the skill picks
them up automatically.

### Option B — Reuse `glab` credentials

If you already use the [`glab`](https://gitlab.com/gitlab-org/cli) CLI:

```bash
glab auth login
```

The skill will read the host and token from `~/.config/glab-cli/config.yml`.

---

## Required token permissions

Create a PAT at:

- **gitlab.com**: <https://gitlab.com/-/user_settings/personal_access_tokens>
- **Self-hosted**: `https://<your-host>/-/user_settings/personal_access_tokens`

### Minimum scope

| Scope      | Required | Why                                                                 |
| ---------- | :------: | ------------------------------------------------------------------- |
| `read_api` |    ✅    | Read MRs, discussions, changes, and pipeline status via the REST API |

`read_api` is sufficient — the skill performs **no writes**. Do **not** grant
`api`, `write_repository`, or admin scopes unless you need them for other tools.

### Other token settings

- **Expiration**: pick the shortest practical lifetime (GitLab requires one).
- **Role / membership**: the token inherits your user's access. You'll only see
  MRs in projects you can already view.
- **Group / project tokens**: not suitable here — the report is keyed off
  `/user` (the "current user"), which a group/project token cannot represent.
  Use a **personal** access token.

### What the skill calls

For reference/audit, the script hits only these read-only endpoints:

- `GET /user`
- `GET /merge_requests?scope=created_by_me&state=opened`
- `GET /merge_requests?scope=all&reviewer_username=<me>&state=opened`
- `GET /projects/:id/merge_requests/:iid` (detail — for `head_pipeline`, `has_conflicts`)
- `GET /projects/:id/merge_requests/:iid/pipelines` (fallback when detail has no pipeline)
- `GET /projects/:id/merge_requests/:iid/diffs` (paginated; falls back to `/changes` on older instances)
- `GET /projects/:id/merge_requests/:iid/approvals`
- `GET /projects/:id/merge_requests/:iid/discussions`
- `GET /projects/:id` (to detect archived projects; their MRs are hidden from the report)

---

## Verifying your setup

```bash
# Run from the skill directory so the relative script path resolves.
cd /path/to/gitlab-mr-report && python3 ./scripts/mr_report.py
```

Expected outcomes:

- ✅ Prints a Markdown report to stdout.
- ❌ `ERROR: No GitLab token found` → set `GITLAB_TOKEN` or run `glab auth login`.
- ❌ `ERROR: GitLab returned 401 ...` → token is invalid or expired.
- ❌ `ERROR: GitLab returned 403 ...` → token is missing the `read_api` scope.
- ❌ DNS / connection error → check `GITLAB_HOST` (hostname only, no `https://`).

---

## Tuning

Module-level constants at the top of `scripts/mr_report.py`:

- `STALE_DAYS` (default `7`) — threshold for the "stale" flag.
- `HTTP_TIMEOUT` (default `30`) — per-request timeout, in seconds.
- `PER_PAGE` (default `100`) — GitLab API page size for paginated calls.
- `USER_AGENT` (default `gitlab-mr-report`) — sent on every request.

---

## Privacy note

The token is read from your environment / `glab` config and sent only to the
configured GitLab host over HTTPS. Nothing is written to disk by the skill.
