# ~/develop layout

Most top-level directories named after a git forge host (`github.com/`, `gitlab.com/`, `code.badjware.dev/`, ...) are [gitforgefs](https://github.com/badjware/gitforgefs) FUSE mounts. Other top-level entries (`workspaces/`, scratch folders, loose files) are plain directories.

## How a gitforgefs mount is organized

```
~/develop/<forge-host>/<user-or-org-or-group>/[<subgroup>/...]<repo>/
```

- Every user, organization, or group on the forge is a directory. GitLab subgroups nest as subdirectories.
- Every repository is an entry inside its owner's directory.
- Archived repositories are hidden: their name is prefixed with `.`
- The directory tree itself lives only in memory and comes from the forge API. You cannot create, rename, or delete user/org/repo entries.
- Translating a repository url to a path is straightforward: `https://<forge-host>/<user-or-org>/<repo>` becomes `~/develop/<forge-host>/<user-or-org>/<repo>`.

## Caveats

- The first access to a repository triggers the creation of an empty clone. You may need to `git pull` to download the content from the remote.
- The listing is cached forever. If a repository was created or renamed on the forge and is missing, run `touch .refresh` inside the parent directory to force a refresh.
- If a directory is empty the mount may be down. Flag the issue to the user if it happens.
