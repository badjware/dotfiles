---
name: update-chezmoi-pinned-externals
description: Bump the pinned file externals in the chezmoi dotfiles repo (home/.chezmoiexternals/install_scripts.toml and home/.chezmoiexternals/appimages.toml) to their latest release and refresh the sha256 checksums. Use when chezmoi apply fails with a checksum mismatch on a .cache/install/*.sh or Applications/*.AppImage external, or when asked to update the installers or AppImages.
---

## When to use
The chezmoi source repo is `~/.local/share/chezmoi` with `.chezmoiroot = home`. Use this skill for the `type = "file"` externals with a `checksum.sha256`:
- `home/.chezmoiexternals/install_scripts.toml`: installer scripts (pyenv, pay-respects, starship, mirrord).
- `home/.chezmoiexternals/appimages.toml`: AppImages in `~/Applications` (FreeCAD, Logseq-OG, Moonlight, Obsidian, dbgate).

Not for the git-repo externals (tmux, vim, zsh), which track branches without checksums.

## Procedure
1. Read both files and list each entry's `url` and `checksum.sha256`. Each url is pinned to a release tag, except pyenv-installer which tracks `master`.
2. For each repo, get the latest release with a read-only GET on `https://api.github.com/repos/<owner>/<repo>/releases/latest` and read `.tag_name` and `.assets[]` with jq. Anonymous requests are limited to 60/hour; a 403 means rate limited. If a GitHub token exists in the environment, authenticate with it; otherwise ask the user to add one.
3. Installer scripts (`install_scripts.toml`), url is `raw.githubusercontent.com/<owner>/<repo>/<tag>/<path>`:
   - `iffse/pay-respects` -> `install.sh` (tags like `v0.8.8`)
   - `starship/starship` -> `install/install.sh` (tags like `v1.26.0`). Do not use the starship.rs install URL, it moves.
   - `metalbear-co/mirrord` -> `scripts/install.sh` (tags have no `v` prefix, like `3.270.0`)
   - `pyenv/pyenv-installer` -> `bin/pyenv-installer`. No releases (`releases/latest` returns 404; the only tag is from 2015), so the url stays on `master` and only the checksum changes. Pin to a commit SHA from `/repos/pyenv/pyenv-installer/commits/master` only if the user asks.
   Download each script and hash it with `sha256sum`. A 404 means the script moved; find the new path in the repo tree at that tag.
4. AppImages (`appimages.toml`), url is the release asset `browser_download_url`:
   - `FreeCAD/FreeCAD` -> `FreeCAD_<ver>-Linux-x86_64-py311.AppImage` (tags have no `v` prefix). The `py311` suffix can change; pick the x86_64 asset.
   - `logseq/og` -> `Logseq-OG-linux-x64-<ver>.AppImage`. This is the file-based Logseq. Do not switch to `logseq/logseq`, which is the DB version (2.x).
   - `moonlight-stream/moonlight-qt` -> `Moonlight-<ver>-x86_64.AppImage`
   - `obsidianmd/obsidian-releases` -> `Obsidian-<ver>.AppImage` (not the `-arm64` one)
   - `dbgate/dbgate` -> `dbgate-<ver>-linux_x86_64.AppImage`. Not `dbgate-latest*` (moves) and not `dbgate-premium-*`.
   Take the checksum from the asset's `digest` field (`sha256:<hex>`), so the large files don't need to be downloaded. Only if `digest` is null, download the asset and hash it.
5. Download files only to hash them. Never execute a downloaded script or AppImage, and never pipe one to a shell.
6. Update `url` and `checksum.sha256` for each entry with the edit tool. Keep the target path and the other fields (`type = "file"`, `executable = true`) unchanged. AppImage targets use stable names without versions (`Applications/Obsidian.AppImage`), so a bump replaces the file in place and the desktop entry stays valid.
7. Report the old and new version plus the new sha256 for each entry. Do not commit unless the user explicitly asks.

## Pitfalls
- Pinning the installer does not pin the binary. The pay-respects and mirrord installers fetch the latest release at run time; starship takes `--version` and mirrord reads a `VERSION` env var. Mention this if the user wants reproducible versions.
- Do not add `exact = true` to these entries; it only applies to archive externals.
- Do not version the AppImage target names. chezmoi never deletes the previous file when a target name changes, and `home/.chezmoiscripts/run_onchange_after_install_appimage_desktop_entries.sh.tmpl` names the desktop entry after the file.
- chezmoi caches each external under `~/.cache/chezmoi/external/`, keyed by the sha256 of the url. After a bump the old version's cache file stays there; for AppImages that is hundreds of MB. Mention it in the report so the user can clear it.
- chezmoi may not be installed in the agent container, so the change may not be verifiable with chezmoi. Matching the checksum against the asset digest or the downloaded file is the check.
- `releases/latest` skips prereleases and nightlies. Keep users on stable releases unless they ask otherwise.
- `home/.chezmoiscripts/run_onchange_after_packages.sh.tmpl` only runs the installer scripts when the command is missing (`command -v`), so a new installer pin does not upgrade an already installed tool.

## Verification
1. Every `checksum.sha256` equals the release asset `digest` (AppImages) or the sha256 of the file downloaded from `url` (scripts).
2. Every url contains a release tag, not `main`/`master`, a `latest` asset, or a moving domain. pyenv-installer is the exception and stays on `master` unless pinned to a commit.
3. `git diff home/.chezmoiexternals/` shows only `url` and `checksum.sha256` lines changed.
