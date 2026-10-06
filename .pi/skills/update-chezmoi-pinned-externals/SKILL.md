---
name: update-chezmoi-pinned-externals
description: Bump every checksum-pinned file external in the chezmoi dotfiles repo (any home/.chezmoiexternals/* entry with checksum.sha256) to its latest GitHub release and refresh the sha256. Use when chezmoi apply fails with a checksum mismatch on an external, or when asked to update the installers, AppImages, or pinned externals.
---

## When to use
The chezmoi source repo is `~/.local/share/chezmoi` with `.chezmoiroot = home`. Use this skill for `type = "file"` externals that carry a `checksum.sha256`, in any file under `home/.chezmoiexternals/`. Do not assume a fixed list of files or entries: discover them every time.

Not for `git-repo`/`archive` externals without checksums (tmux, vim, zsh) or file externals without a checksum (wallpaper). They track branches or moving URLs by design.

## Procedure
1. Discover entries: `rg -l 'checksum\.sha256' home/.chezmoiexternals/`, then read each matching file. For each entry, record the target (the `["..."]` header), `url`, `checksum.sha256`, and any `# update:` comment lines directly above the header. An `# update:` comment is a per-entry rule that overrides the generic steps below; follow it.
2. Classify each url:
   - **Raw script**: `https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>`. `<ref>` is a tag, or a commit SHA when the repo has no releases.
   - **Release asset**: `https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`.
   - **Anything else**: not handled automatically. Report it and ask the user how to track it.
3. Find the latest stable version per repo:
   - Preferred: GET `https://api.github.com/repos/<owner>/<repo>/releases/latest`, read `.tag_name` and `.assets[]` (`name`, `digest`, `browser_download_url`) with jq. Use `GITHUB_TOKEN`/`GH_TOKEN` from the environment if set (`Authorization: Bearer`). Anonymous calls are limited to 60/hour; a 403 means rate limited (check `https://api.github.com/rate_limit`, `.rate.reset` is a unix time).
   - Fallback without API: `git ls-remote --tags --refs https://github.com/<owner>/<repo>`, keep tags with the same shape as the pinned one (same `v` prefix or none, `X.Y.Z`, no `-rc`/`-beta`), `sort -V | tail -1`. Filter by prefix before sorting; mixed `v`/no-`v` tags sort wrong (mirrord has both, the current ones have no `v`).
   - A 404 on `releases/latest` means no releases. Pin `<ref>` to the default branch's latest commit SHA (`git ls-remote https://github.com/<owner>/<repo> HEAD`). Never leave a branch name in the url.
4. If the latest tag equals the pinned tag, the entry is current. Still verify the checksum (step 6) if cheap.
5. Build the new url:
   - Raw script: replace `<ref>` with the new tag, keep `<path>`. A 404 means the script moved; find it in the repo tree at the new tag.
   - Release asset: derive the new asset name by replacing the old version string in `<asset>` with the new one (version = tag without leading `v`), then confirm it exists in `.assets[]`. If it does not, pick the asset matching the same platform/arch/extension (x86_64/x64, `.AppImage`, not `arm64`/`aarch64`). Use its `browser_download_url`.
6. Compute the checksum:
   - Release asset: take the asset's `digest` (`sha256:<hex>`) from the API, so large files are not downloaded. If `digest` is null or the API is unavailable, download to `/tmp` and `sha256sum`; for files over ~100 MB, ask the user first or wait for the rate limit reset.
   - Raw script: download with `curl -sfL` and pipe to `sha256sum` (raw.githubusercontent.com is not API rate limited).
7. Never execute a downloaded file or pipe one to a shell. Download only to hash.
8. Edit only `url` and `checksum.sha256` with the edit tool. Keep the target path and all other fields unchanged.
9. Report a table: entry, old version, new version, checksum status (updated / matches / not verified and why). Do not commit unless the user explicitly asks.

## Per-entry rules
Repo-specific exceptions live in the TOML as `# update: <rule>` comments directly above the entry header, not in this skill. When you discover a new exception while updating (an asset name that changed shape, a moving url, a repo to avoid), add or amend the entry's `# update:` comment in the same edit. Keep comments one line each, imperative, and only for exceptions; entries handled by the generic steps need none.

## Pitfalls
- Pinning an installer does not pin the binary. Installers like pay-respects and mirrord fetch the latest release at run time; starship takes `--version`, mirrord reads a `VERSION` env var. Mention this if the user wants reproducible versions.
- Do not add `exact = true` to file externals; it only applies to archives.
- Do not version target names (`Applications/Obsidian.AppImage`). chezmoi never deletes the old file when a target name changes, and `home/.chezmoiscripts/run_onchange_after_install_appimage_desktop_entries.sh.tmpl` names the desktop entry after the file.
- chezmoi caches each external under `~/.cache/chezmoi/external/`, keyed by the sha256 of the url. Old versions stay there (hundreds of MB for AppImages). Mention it so the user can clear it.
- chezmoi may not be installed in the agent container. Matching the checksum against the asset digest or downloaded file is the check.
- `releases/latest` skips prereleases and nightlies. Keep stable releases unless asked otherwise.
- `home/.chezmoiscripts/run_onchange_after_packages.sh.tmpl` only runs installer scripts when the command is missing (`command -v`), so a new installer pin does not upgrade an installed tool.

## Verification
1. Every discovered entry appears in the report, including unhandled ones.
2. Every `checksum.sha256` equals the release asset `digest` or the sha256 of the file downloaded from `url`.
3. Every url contains a release tag or, for repos without releases, a commit SHA. No branch names, `latest` assets, or moving domains.
4. `git diff home/.chezmoiexternals/` shows only `url` and `checksum.sha256` lines changed.
