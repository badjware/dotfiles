// PI WEB server plugin for "Jump to project": lists the directories where Pi
// sessions ran, so the browser dialog can offer them as unregistered projects.

import { open, readdir, readFile, realpath, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { isAbsolute, join } from "node:path";

/**
 * Resolve the Pi session directory the same way Pi does, minus the CLI flag:
 * PI_CODING_AGENT_SESSION_DIR, then an absolute `sessionDir` setting, then the
 * default `<agent dir>/sessions`. A relative `sessionDir` depends on the working
 * directory of each Pi run, so it is ignored.
 */
async function sessionDirectory() {
  const env = process.env["PI_CODING_AGENT_SESSION_DIR"];
  if (env) return env;
  const agentDir = process.env["PI_CODING_AGENT_DIR"] || join(homedir(), ".pi", "agent");
  try {
    const { sessionDir } = JSON.parse(await readFile(join(agentDir, "settings.json"), "utf8"));
    if (typeof sessionDir === "string" && isAbsolute(sessionDir)) return sessionDir;
  } catch {
    // No readable settings: use the default.
  }
  return join(agentDir, "sessions");
}

/** Return the `cwd` from the session header (the first line of the file), or undefined. */
async function sessionCwd(file) {
  const handle = await open(file, "r");
  try {
    const { buffer, bytesRead } = await handle.read(Buffer.alloc(4096), 0, 4096, 0);
    const line = buffer.toString("utf8", 0, bytesRead).split("\n", 1)[0];
    const header = JSON.parse(line);
    return header.type === "session" && typeof header.cwd === "string" ? header.cwd : undefined;
  } finally {
    await handle.close();
  }
}

/**
 * List existing session directories outside /tmp as `{ path, lastSessionAt }`,
 * newest first. Paths are resolved with realpath to match registered project paths.
 */
async function listCandidates(signal) {
  const root = await sessionDirectory();
  const latest = new Map();
  for (const group of await readdir(root, { withFileTypes: true })) {
    if (!group.isDirectory()) continue;
    for (const name of await readdir(join(root, group.name))) {
      signal.throwIfAborted();
      if (!name.endsWith(".jsonl")) continue;
      const file = join(root, group.name, name);
      try {
        const cwd = await sessionCwd(file);
        if (cwd === undefined) continue;
        const { mtimeMs } = await stat(file);
        if (mtimeMs > (latest.get(cwd) ?? 0)) latest.set(cwd, mtimeMs);
      } catch {
        // Unreadable or malformed session file: skip it.
      }
    }
  }
  const candidates = new Map();
  for (const [cwd, mtimeMs] of latest) {
    let path;
    try {
      path = await realpath(cwd);
      if (!(await stat(path)).isDirectory()) continue;
    } catch {
      continue; // The directory no longer exists.
    }
    if (path === "/tmp" || path.startsWith("/tmp/")) continue;
    if (mtimeMs > (candidates.get(path) ?? 0)) candidates.set(path, mtimeMs);
  }
  return [...candidates]
    .sort((a, b) => b[1] - a[1])
    .map(([path, mtimeMs]) => ({ path, lastSessionAt: new Date(mtimeMs).toISOString() }));
}

export default {
  apiVersion: 5,
  name: "Jump to project",
  activate() {
    return {
      peer: {
        request({ operation, signal }) {
          if (operation !== "candidates") throw new Error(`Unknown operation: ${operation}`);
          return listCandidates(signal);
        },
      },
    };
  },
};
